package de.bluelight.ueberzeitrechner.viewmodel

import android.app.Application
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.bluelight.ueberzeitrechner.data.AppDatabase
import de.bluelight.ueberzeitrechner.data.BereitschaftEntryEntity
import de.bluelight.ueberzeitrechner.data.EntriesDao
import de.bluelight.ueberzeitrechner.data.WorkEntryEntity
import de.bluelight.ueberzeitrechner.logic.HolidayManager
import de.bluelight.ueberzeitrechner.logic.TimeCalculator
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File
import java.io.FileOutputStream
import java.time.LocalDate
import java.time.format.DateTimeFormatter

sealed class ImportStatus {
    object Idle : ImportStatus()
    object InProgress : ImportStatus()
    data class Success(val workEntries: Int, val bereitschaftEntries: Int) : ImportStatus()
    data class Error(val message: String) : ImportStatus()
}

sealed class SyncStatus {
    object Idle : SyncStatus()
    object InProgress : SyncStatus()
    data class Success(val timestampMs: Long) : SyncStatus()
    data class Error(val message: String) : SyncStatus()
    object NotLinked : SyncStatus()
}

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val sharedPrefs: SharedPreferences =
        application.getSharedPreferences("ueberzeit_settings", Context.MODE_PRIVATE)

    private val dao: EntriesDao = AppDatabase.getDatabase(application).entriesDao()

    val entries: StateFlow<List<WorkEntryEntity>> = dao.getAllEntriesFlow()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val bereitschaft: StateFlow<List<BereitschaftEntryEntity>> = dao.getAllBereitschaftFlow()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    // --- Exposed Application Settings ---
    private val _targetWorkTime = MutableStateFlow(sharedPrefs.getInt("target_work_time", 480))
    val targetWorkTime: StateFlow<Int> = _targetWorkTime.asStateFlow()

    private val _autoBreak = MutableStateFlow(sharedPrefs.getBoolean("auto_break", true))
    val autoBreak: StateFlow<Boolean> = _autoBreak.asStateFlow()

    private val _country = MutableStateFlow(sharedPrefs.getString("country", "DE") ?: "DE")
    val country: StateFlow<String> = _country.asStateFlow()

    private val _stateCode = MutableStateFlow(sharedPrefs.getString("state", "BW") ?: "BW")
    val stateCode: StateFlow<String> = _stateCode.asStateFlow()

    private val _workingDays = MutableStateFlow(
        sharedPrefs.getStringSet("working_days", setOf("1", "2", "3", "4", "5"))
            ?.map { it.toInt() }?.toSet() ?: setOf(1, 2, 3, 4, 5)
    )
    val workingDays: StateFlow<Set<Int>> = _workingDays.asStateFlow()

    private val _importStatus = MutableStateFlow<ImportStatus>(ImportStatus.Idle)
    val importStatus: StateFlow<ImportStatus> = _importStatus.asStateFlow()

    private val _syncStatus = MutableStateFlow<SyncStatus>(
        if (sharedPrefs.getString("source_db_uri", null) == null) SyncStatus.NotLinked
        else {
            val lastTs = sharedPrefs.getLong("last_sync_ms", 0L)
            if (lastTs > 0) SyncStatus.Success(lastTs) else SyncStatus.Idle
        }
    )
    val syncStatus: StateFlow<SyncStatus> = _syncStatus.asStateFlow()

    private val _linkedUriLabel = MutableStateFlow(sharedPrefs.getString("source_db_label", null))
    val linkedUriLabel: StateFlow<String?> = _linkedUriLabel.asStateFlow()

    private val exportMutex = Mutex()

    init {
        // Clean up orphaned state from the old external-DB mechanism so the app
        // never tries to reopen an imported file that Room can't validate.
        sharedPrefs.getString("custom_db_path", null)?.let {
            sharedPrefs.edit().remove("custom_db_path").apply()
            runCatching { File(it).delete() }
        }
    }

    // --- Setting Updates ---
    fun updateTargetWorkTime(minutes: Int) {
        sharedPrefs.edit().putInt("target_work_time", minutes).apply()
        _targetWorkTime.value = minutes
    }

    fun updateAutoBreak(enabled: Boolean) {
        sharedPrefs.edit().putBoolean("auto_break", enabled).apply()
        _autoBreak.value = enabled
    }

    fun updateRegion(country: String, state: String) {
        sharedPrefs.edit().putString("country", country).putString("state", state).apply()
        _country.value = country
        _stateCode.value = state
    }

    fun updateWorkingDays(days: Set<Int>) {
        sharedPrefs.edit().putStringSet("working_days", days.map { it.toString() }.toSet()).apply()
        _workingDays.value = days
    }

    /**
     * Resolves the target working minutes for a specific date, factoring in holidays and weekends.
     */
    fun getTargetMinutesForDate(dateStr: String, customTarget: Int = -1): Int {
        if (customTarget != -1) return customTarget

        val date = try {
            LocalDate.parse(dateStr, DateTimeFormatter.ISO_LOCAL_DATE)
        } catch (e: Exception) {
            return _targetWorkTime.value
        }

        val holidays = HolidayManager.getGermanHolidays(date.year, _stateCode.value)
        if (holidays.containsKey(dateStr)) return 0

        val dayOfWeek = date.dayOfWeek.value
        if (!workingDays.value.contains(dayOfWeek)) return 0

        if ((date.monthValue == 12 && date.dayOfMonth == 24) || (date.monthValue == 12 && date.dayOfMonth == 31)) {
            return 240
        }

        return _targetWorkTime.value
    }

    // Every entry's `minutes` is the per-entry overtime delta (Python desktop semantics):
    // 0 for non-last timed entries of a day, the day's net-minus-target for the last timed
    // entry, and the user-entered value for manual entries. `recalculateDay()` keeps that
    // invariant whenever entries change.
    val overallBalance: StateFlow<Int> = entries.map { it.sumOf { e -> e.minutes } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)

    // --- DB Operations ---
    fun addWorkEntry(date: String, start: String?, end: String?, pause: Int, reason: String?, target: Int = -1) {
        viewModelScope.launch(Dispatchers.IO) {
            val entity = WorkEntryEntity(
                date = date,
                start = start,
                end = end,
                pause = pause,
                minutes = 0, // recalculateDay assigns the real overtime delta
                reason = reason,
                targetMinutes = target
            )
            dao.insertEntry(entity)
            recalculateDay(date)
            exportToSourceFile()
        }
    }

    /**
     * Adds a manual entry: no start/end times, the user just enters the per-day overtime
     * delta in minutes (positive = overtime, negative = undertime). Mirrors the desktop's
     * "Manueller Eintrag" workflow used for travel time, comp time, etc.
     */
    fun addManualEntry(date: String, minutes: Int, reason: String?, target: Int = -1) {
        viewModelScope.launch(Dispatchers.IO) {
            val entity = WorkEntryEntity(
                date = date,
                start = null,
                end = null,
                pause = 0,
                minutes = minutes,
                reason = reason,
                targetMinutes = target
            )
            dao.insertEntry(entity)
            // If the day also has timed entries, a new custom target on this row could shift
            // their overtime distribution — recalc keeps the invariants.
            recalculateDay(date)
            exportToSourceFile()
        }
    }

    fun updateWorkEntry(entry: WorkEntryEntity) {
        viewModelScope.launch(Dispatchers.IO) {
            val oldDate = dao.getEntryById(entry.id)?.date
            dao.updateEntry(entry)
            recalculateDay(entry.date)
            if (oldDate != null && oldDate != entry.date) {
                recalculateDay(oldDate)
            }
            exportToSourceFile()
        }
    }

    fun deleteWorkEntry(id: Int) {
        viewModelScope.launch(Dispatchers.IO) {
            val date = dao.getEntryById(id)?.date
            dao.deleteEntryById(id)
            date?.let { recalculateDay(it) }
            exportToSourceFile()
        }
    }

    /**
     * Mirrors the desktop's `recalculate_day`: timed entries get their per-entry overtime
     * (0 for non-last entries, the day's net-minus-target for the last entry). Manual
     * entries are left untouched since their `minutes` already represents the user's delta.
     */
    private suspend fun recalculateDay(date: String) {
        val dayEntries = dao.getEntriesByDate(date)
        val timed = dayEntries.filter { !it.start.isNullOrEmpty() && !it.end.isNullOrEmpty() }
        if (timed.isEmpty()) return

        val customTarget = dayEntries.firstOrNull { it.targetMinutes != -1 }?.targetMinutes ?: -1
        val target = getTargetMinutesForDate(date, customTarget)

        val (results, _) = TimeCalculator.calculateTimedEntries(
            timed,
            target,
            600,
            _autoBreak.value
        )
        for (e in timed) {
            val (pauseMins, overtimeMins) = results[e.id] ?: continue
            if (e.pause != pauseMins || e.minutes != overtimeMins) {
                dao.updateEntry(e.copy(pause = pauseMins, minutes = overtimeMins))
            }
        }
    }

    fun addBereitschaft(date: String, endDate: String?, start: String?, end: String?, note: String?) {
        viewModelScope.launch(Dispatchers.IO) {
            val entity = BereitschaftEntryEntity(
                date = date,
                endDate = endDate ?: date,
                start = start,
                end = end,
                note = note
            )
            dao.insertBereitschaft(entity)
            exportToSourceFile()
        }
    }

    fun updateBereitschaft(entry: BereitschaftEntryEntity) {
        viewModelScope.launch(Dispatchers.IO) {
            dao.updateBereitschaft(entry)
            exportToSourceFile()
        }
    }

    fun deleteBereitschaft(id: Int) {
        viewModelScope.launch(Dispatchers.IO) {
            dao.deleteBereitschaftById(id)
            exportToSourceFile()
        }
    }

    fun acknowledgeImportStatus() {
        _importStatus.value = ImportStatus.Idle
    }

    /**
     * Read a raw SQLite file (created by the desktop Python app) and copy its rows into
     * the local Room database. Avoids letting Room validate the foreign schema, which
     * would otherwise crash on NOT NULL / room_master_table mismatches.
     *
     * If the URI grants persistable read+write permission, it's remembered so that
     * later edits can be written back to the source file via [exportToSourceFile].
     */
    fun importExternalDatabase(context: Context, uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            _importStatus.value = ImportStatus.InProgress
            var tempFile: File? = null
            var srcDb: SQLiteDatabase? = null
            try {
                tempFile = File(context.cacheDir, "import_${System.currentTimeMillis()}.db")
                val input = context.contentResolver.openInputStream(uri)
                    ?: throw IllegalStateException("Datei konnte nicht geöffnet werden")
                input.use { ins ->
                    FileOutputStream(tempFile).use { out -> ins.copyTo(out) }
                }

                srcDb = SQLiteDatabase.openDatabase(
                    tempFile.absolutePath,
                    null,
                    SQLiteDatabase.OPEN_READONLY
                )

                // Load all data before touching the local DB so we can replace atomically.
                val workEntries = readEntriesFromExternalDb(srcDb)
                val berEntries = readBereitschaftFromExternalDb(srcDb)

                // Replace atomically via a transaction; if anything fails the local DB
                // keeps its previous data.
                dao.replaceAllEntries(workEntries)
                dao.replaceAllBereitschaft(berEntries)
                // Try to keep the URI for write-back. Fails silently if the provider
                // didn't flag the URI as persistable — then auto-sync stays disabled
                // but import itself still succeeded.
                rememberSourceUri(context, uri)
                _importStatus.value = ImportStatus.Success(workEntries.size, berEntries.size)
            } catch (e: Exception) {
                _importStatus.value = ImportStatus.Error(
                    e.message ?: e::class.java.simpleName
                )
            } finally {
                runCatching { srcDb?.close() }
                runCatching { tempFile?.delete() }
            }
        }
    }

    private fun rememberSourceUri(context: Context, uri: Uri) {
        val flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        val granted = runCatching {
            context.contentResolver.takePersistableUriPermission(uri, flags)
        }.isSuccess
        if (!granted) {
            // Provider didn't allow persisting — leave the previously stored URI in place
            // (if any) and don't claim auto-sync.
            return
        }
        val label = displayLabelFor(context, uri)
        sharedPrefs.edit()
            .putString("source_db_uri", uri.toString())
            .putString("source_db_label", label)
            .remove("last_sync_ms")
            .apply()
        _linkedUriLabel.value = label
        _syncStatus.value = SyncStatus.Idle
    }

    private fun displayLabelFor(context: Context, uri: Uri): String {
        val name = runCatching {
            context.contentResolver.query(uri, null, null, null, null)?.use { c ->
                val idx = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                if (idx >= 0 && c.moveToFirst()) c.getString(idx) else null
            }
        }.getOrNull()
        return name ?: uri.lastPathSegment ?: uri.toString()
    }

    fun manualExport() {
        viewModelScope.launch(Dispatchers.IO) {
            exportToSourceFile()
        }
    }

    fun unlinkSourceFile() {
        viewModelScope.launch(Dispatchers.IO) {
            val uriStr = sharedPrefs.getString("source_db_uri", null)
            if (uriStr != null) {
                runCatching {
                    getApplication<Application>().contentResolver.releasePersistableUriPermission(
                        Uri.parse(uriStr),
                        Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                    )
                }
            }
            sharedPrefs.edit()
                .remove("source_db_uri")
                .remove("source_db_label")
                .remove("last_sync_ms")
                .apply()
            _linkedUriLabel.value = null
            _syncStatus.value = SyncStatus.NotLinked
        }
    }

    /**
     * Writes the current Room contents back to the linked source URI as a fresh SQLite
     * file that matches the desktop's schema. No-op if no URI is linked.
     */
    private suspend fun exportToSourceFile() {
        val context = getApplication<Application>()
        val uriStr = sharedPrefs.getString("source_db_uri", null)
        if (uriStr == null) {
            _syncStatus.value = SyncStatus.NotLinked
            return
        }
        val uri = Uri.parse(uriStr)

        exportMutex.withLock {
            _syncStatus.value = SyncStatus.InProgress
            var tempFile: File? = null
            try {
                tempFile = File(context.cacheDir, "export_${System.currentTimeMillis()}.db")
                SQLiteDatabase.openOrCreateDatabase(tempFile, null).use { dest ->
                    dest.execSQL(
                        """
                        CREATE TABLE entries (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT NOT NULL,
                            start TEXT,
                            end TEXT,
                            pause INTEGER,
                            minutes INTEGER,
                            reason TEXT,
                            target_minutes INTEGER DEFAULT -1
                        )
                        """.trimIndent()
                    )
                    dest.execSQL(
                        """
                        CREATE TABLE bereitschaft_entries (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT NOT NULL,
                            start TEXT,
                            end TEXT,
                            note TEXT,
                            end_date TEXT
                        )
                        """.trimIndent()
                    )
                    dest.beginTransaction()
                    try {
                        for (e in dao.getAllEntries()) {
                            val cv = ContentValues().apply {
                                put("id", e.id)
                                put("date", e.date)
                                put("start", e.start)
                                put("end", e.end)
                                put("pause", e.pause)
                                put("minutes", e.minutes)
                                put("reason", e.reason)
                                put("target_minutes", e.targetMinutes)
                            }
                            dest.insert("entries", null, cv)
                        }
                        for (b in dao.getAllBereitschaft()) {
                            val cv = ContentValues().apply {
                                put("id", b.id)
                                put("date", b.date)
                                put("start", b.start)
                                put("end", b.end)
                                put("note", b.note)
                                put("end_date", b.endDate)
                            }
                            dest.insert("bereitschaft_entries", null, cv)
                        }
                        dest.setTransactionSuccessful()
                    } finally {
                        dest.endTransaction()
                    }
                }

                val out = context.contentResolver.openOutputStream(uri, "wt")
                    ?: throw IllegalStateException(
                        "Datei nicht beschreibbar — Speicherort unterstützt evtl. keinen Schreibzugriff"
                    )
                out.use { stream ->
                    tempFile.inputStream().use { it.copyTo(stream) }
                }

                val now = System.currentTimeMillis()
                sharedPrefs.edit().putLong("last_sync_ms", now).apply()
                _syncStatus.value = SyncStatus.Success(now)
            } catch (e: Exception) {
                _syncStatus.value = SyncStatus.Error(e.message ?: e::class.java.simpleName)
            } finally {
                runCatching { tempFile?.delete() }
            }
        }
    }

    private suspend fun readEntriesFromExternalDb(srcDb: SQLiteDatabase): List<WorkEntryEntity> {
        val result = mutableListOf<WorkEntryEntity>()
        val hasTable = srcDb.rawQuery(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'",
            null
        ).use { it.count > 0 }
        if (!hasTable) return result

        val cols = srcDb.rawQuery("PRAGMA table_info(entries)", null).use { c ->
            buildSet { while (c.moveToNext()) add(c.getString(1)) }
        }
        val hasTarget = "target_minutes" in cols

        val sql = "SELECT date, start, end, pause, minutes, reason" +
                (if (hasTarget) ", target_minutes" else "") + " FROM entries"

        srcDb.rawQuery(sql, null).use { c ->
            while (c.moveToNext()) {
                val date = c.getString(0) ?: continue
                result += WorkEntryEntity(
                    date = date,
                    start = c.getString(1),
                    end = c.getString(2),
                    pause = if (c.isNull(3)) 0 else c.getInt(3),
                    minutes = if (c.isNull(4)) 0 else c.getInt(4),
                    reason = c.getString(5),
                    targetMinutes = if (hasTarget && !c.isNull(6)) c.getInt(6) else -1
                )
            }
        }
        return result
    }

    private suspend fun readBereitschaftFromExternalDb(srcDb: SQLiteDatabase): List<BereitschaftEntryEntity> {
        val result = mutableListOf<BereitschaftEntryEntity>()
        val hasTable = srcDb.rawQuery(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bereitschaft_entries'",
            null
        ).use { it.count > 0 }
        if (!hasTable) return result

        val cols = srcDb.rawQuery("PRAGMA table_info(bereitschaft_entries)", null).use { c ->
            buildSet { while (c.moveToNext()) add(c.getString(1)) }
        }
        val hasEndDate = "end_date" in cols

        val sql = "SELECT date, start, end, note" +
                (if (hasEndDate) ", end_date" else "") + " FROM bereitschaft_entries"

        srcDb.rawQuery(sql, null).use { c ->
            while (c.moveToNext()) {
                val date = c.getString(0) ?: continue
                result += BereitschaftEntryEntity(
                    date = date,
                    start = c.getString(1),
                    end = c.getString(2),
                    note = c.getString(3),
                    endDate = if (hasEndDate) c.getString(4) else null
                )
            }
        }
        return result
    }
}
