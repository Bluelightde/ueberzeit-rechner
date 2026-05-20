package de.bluelight.ueberzeitrechner.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface EntriesDao {

    // --- Work Entries ---
    @Query("SELECT * FROM entries ORDER BY date DESC, start DESC")
    fun getAllEntriesFlow(): Flow<List<WorkEntryEntity>>

    @Query("SELECT * FROM entries ORDER BY date DESC, start DESC")
    suspend fun getAllEntries(): List<WorkEntryEntity>

    @Query("SELECT * FROM entries WHERE date = :date ORDER BY start ASC")
    suspend fun getEntriesByDate(date: String): List<WorkEntryEntity>

    @Query("SELECT * FROM entries WHERE id = :id LIMIT 1")
    suspend fun getEntryById(id: Int): WorkEntryEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertEntry(entry: WorkEntryEntity): Long

    @Update
    suspend fun updateEntry(entry: WorkEntryEntity)

    @Query("DELETE FROM entries WHERE id = :id")
    suspend fun deleteEntryById(id: Int)

    // --- Standby / Bereitschaft Entries ---
    @Query("SELECT * FROM bereitschaft_entries ORDER BY date DESC")
    fun getAllBereitschaftFlow(): Flow<List<BereitschaftEntryEntity>>

    @Query("SELECT * FROM bereitschaft_entries ORDER BY date DESC")
    suspend fun getAllBereitschaft(): List<BereitschaftEntryEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertBereitschaft(entry: BereitschaftEntryEntity): Long

    @Update
    suspend fun updateBereitschaft(entry: BereitschaftEntryEntity)

    @Query("DELETE FROM bereitschaft_entries WHERE id = :id")
    suspend fun deleteBereitschaftById(id: Int)

    @Query("DELETE FROM entries")
    suspend fun clearEntries()

    @Query("DELETE FROM bereitschaft_entries")
    suspend fun clearBereitschaft()
}
