package de.bluelight.ueberzeitrechner.ui

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.bluelight.ueberzeitrechner.data.BereitschaftEntryEntity
import de.bluelight.ueberzeitrechner.data.WorkEntryEntity
import de.bluelight.ueberzeitrechner.logic.TimeCalculator
import de.bluelight.ueberzeitrechner.ui.theme.ColorInfo
import de.bluelight.ueberzeitrechner.ui.theme.ColorNegative
import de.bluelight.ueberzeitrechner.ui.theme.ColorPositive
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.Calendar
import java.util.Locale
import kotlin.math.abs

@Composable
fun EditEntryDialog(
    entry: WorkEntryEntity,
    autoBreak: Boolean,
    onSave: (WorkEntryEntity) -> Unit,
    onDelete: () -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val initiallyManual = entry.start.isNullOrEmpty() || entry.end.isNullOrEmpty()

    var isManual by remember { mutableStateOf(initiallyManual) }
    var date by remember { mutableStateOf(entry.date) }
    var startTime by remember { mutableStateOf(entry.start.orEmpty().ifEmpty { "08:00" }) }
    var endTime by remember { mutableStateOf(entry.end.orEmpty().ifEmpty { "16:30" }) }
    var pauseMins by remember { mutableStateOf(entry.pause.toString()) }
    var reason by remember { mutableStateOf(entry.reason.orEmpty()) }
    var hasCustomTarget by remember { mutableStateOf(entry.targetMinutes != -1) }
    var customTargetTime by remember {
        mutableStateOf(
            if (entry.targetMinutes != -1) {
                String.format(Locale.ROOT, "%02d:%02d", entry.targetMinutes / 60, entry.targetMinutes % 60)
            } else "08:00"
        )
    }
    val initialAbsMinutes = abs(entry.minutes).takeIf { initiallyManual } ?: 0
    var manualMinutesText by remember {
        mutableStateOf(if (initialAbsMinutes > 0) initialAbsMinutes.toString() else "")
    }
    var manualSignPositive by remember { mutableStateOf(entry.minutes >= 0) }
    var showConfirmDelete by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Eintrag bearbeiten", fontWeight = FontWeight.Bold) },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = isManual, onCheckedChange = { isManual = it })
                    Text("Manueller Eintrag (Plus/Minus-Minuten)", fontSize = 13.sp)
                }

                // Date
                LabeledRow(
                    label = "Datum",
                    value = formatDateDe(date),
                    onClick = {
                        val parsed = runCatching { LocalDate.parse(date) }.getOrDefault(LocalDate.now())
                        val cal = Calendar.getInstance().apply {
                            set(parsed.year, parsed.monthValue - 1, parsed.dayOfMonth)
                        }
                        DatePickerDialog(
                            context,
                            { _, y, m, d -> date = LocalDate.of(y, m + 1, d).toString() },
                            cal.get(Calendar.YEAR),
                            cal.get(Calendar.MONTH),
                            cal.get(Calendar.DAY_OF_MONTH)
                        ).show()
                    }
                )

                if (!isManual) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TimePickerBox(
                            modifier = Modifier.weight(1f),
                            label = "Startzeit",
                            value = startTime,
                            onPicked = { startTime = it }
                        )
                        TimePickerBox(
                            modifier = Modifier.weight(1f),
                            label = "Endzeit",
                            value = endTime,
                            onPicked = { endTime = it }
                        )
                    }

                    if (!autoBreak) {
                        OutlinedTextField(
                            value = pauseMins,
                            onValueChange = { pauseMins = it.filter(Char::isDigit) },
                            label = { Text("Pause (Min.)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            modifier = Modifier.fillMaxWidth()
                        )
                    } else {
                        Text(
                            "Pause wird automatisch berechnet (ArbZG).",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                } else {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        FilterChip(
                            selected = manualSignPositive,
                            onClick = { manualSignPositive = true },
                            label = { Text("+ Plus") }
                        )
                        FilterChip(
                            selected = !manualSignPositive,
                            onClick = { manualSignPositive = false },
                            label = { Text("− Minus") }
                        )
                    }
                    OutlinedTextField(
                        value = manualMinutesText,
                        onValueChange = { manualMinutesText = it.filter(Char::isDigit).take(5) },
                        label = { Text("Minuten") },
                        placeholder = { Text("z. B. 60") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.fillMaxWidth()
                    )
                    val raw = manualMinutesText.toIntOrNull() ?: 0
                    val signed = if (manualSignPositive) raw else -raw
                    if (raw > 0) {
                        Text(
                            "Wird als ${if (signed >= 0) "+" else "−"}${abs(signed) / 60}h ${abs(signed) % 60}m gespeichert.",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Notiz / Tätigkeit (optional)") },
                    modifier = Modifier.fillMaxWidth()
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = hasCustomTarget, onCheckedChange = { hasCustomTarget = it })
                    Text("Individuelles Tagessoll", fontSize = 13.sp)
                }
                if (hasCustomTarget) {
                    LabeledRow(
                        label = "Indiv. Soll",
                        value = customTargetTime,
                        onClick = {
                            val t = runCatching { LocalTime.parse(customTargetTime) }.getOrDefault(LocalTime.of(8, 0))
                            TimePickerDialog(
                                context,
                                { _, h, m -> customTargetTime = String.format(Locale.ROOT, "%02d:%02d", h, m) },
                                t.hour, t.minute, true
                            ).show()
                        }
                    )
                }

                TextButton(
                    onClick = { showConfirmDelete = true },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Eintrag löschen", color = ColorNegative)
                }
            }
        },
        confirmButton = {
            val canSave = !isManual || (manualMinutesText.toIntOrNull() ?: 0) > 0
            TextButton(
                enabled = canSave,
                onClick = {
                    val targetVal = if (hasCustomTarget) {
                        runCatching { LocalTime.parse(customTargetTime) }
                            .map { it.hour * 60 + it.minute }
                            .getOrDefault(-1)
                    } else -1
                    val updated = if (isManual) {
                        val raw = manualMinutesText.toIntOrNull() ?: 0
                        val signed = if (manualSignPositive) raw else -raw
                        entry.copy(
                            date = date,
                            start = null,
                            end = null,
                            pause = 0,
                            minutes = signed,
                            reason = reason.ifBlank { null },
                            targetMinutes = targetVal
                        )
                    } else {
                        val pauseVal = pauseMins.toIntOrNull() ?: 0
                        entry.copy(
                            date = date,
                            start = startTime,
                            end = endTime,
                            pause = pauseVal,
                            reason = reason.ifBlank { null },
                            targetMinutes = targetVal
                        )
                    }
                    onSave(updated)
                }
            ) { Text("Speichern") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Abbrechen") }
        }
    )

    if (showConfirmDelete) {
        AlertDialog(
            onDismissRequest = { showConfirmDelete = false },
            title = { Text("Eintrag löschen?") },
            text = { Text("Dieser Eintrag wird unwiderruflich gelöscht.") },
            confirmButton = {
                TextButton(onClick = {
                    showConfirmDelete = false
                    onDelete()
                }) { Text("Löschen", color = ColorNegative) }
            },
            dismissButton = {
                TextButton(onClick = { showConfirmDelete = false }) { Text("Abbrechen") }
            }
        )
    }
}

@Composable
fun EditBereitschaftDialog(
    entry: BereitschaftEntryEntity,
    onSave: (BereitschaftEntryEntity) -> Unit,
    onDelete: () -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    var startDate by remember { mutableStateOf(entry.date) }
    var endDate by remember { mutableStateOf(entry.endDate ?: entry.date) }
    var startTime by remember { mutableStateOf(entry.start.orEmpty()) }
    var endTime by remember { mutableStateOf(entry.end.orEmpty()) }
    var note by remember { mutableStateOf(entry.note.orEmpty()) }
    var showConfirmDelete by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Bereitschaft bearbeiten", fontWeight = FontWeight.Bold) },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                LabeledRow(
                    label = "Start-Datum",
                    value = formatDateDe(startDate),
                    onClick = {
                        val parsed = runCatching { LocalDate.parse(startDate) }.getOrDefault(LocalDate.now())
                        val cal = Calendar.getInstance().apply {
                            set(parsed.year, parsed.monthValue - 1, parsed.dayOfMonth)
                        }
                        DatePickerDialog(
                            context,
                            { _, y, m, d ->
                                val picked = LocalDate.of(y, m + 1, d)
                                startDate = picked.toString()
                                if (runCatching { LocalDate.parse(endDate) }.getOrNull()?.isBefore(picked) == true) {
                                    endDate = startDate
                                }
                            },
                            cal.get(Calendar.YEAR),
                            cal.get(Calendar.MONTH),
                            cal.get(Calendar.DAY_OF_MONTH)
                        ).show()
                    }
                )
                LabeledRow(
                    label = "End-Datum",
                    value = formatDateDe(endDate),
                    onClick = {
                        val parsed = runCatching { LocalDate.parse(endDate) }.getOrDefault(LocalDate.now())
                        val cal = Calendar.getInstance().apply {
                            set(parsed.year, parsed.monthValue - 1, parsed.dayOfMonth)
                        }
                        DatePickerDialog(
                            context,
                            { _, y, m, d -> endDate = LocalDate.of(y, m + 1, d).toString() },
                            cal.get(Calendar.YEAR),
                            cal.get(Calendar.MONTH),
                            cal.get(Calendar.DAY_OF_MONTH)
                        ).show()
                    }
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TimePickerBox(
                        modifier = Modifier.weight(1f),
                        label = "Startzeit (opt)",
                        value = startTime.ifEmpty { "--:--" },
                        onPicked = { startTime = it }
                    )
                    TimePickerBox(
                        modifier = Modifier.weight(1f),
                        label = "Endzeit (opt)",
                        value = endTime.ifEmpty { "--:--" },
                        onPicked = { endTime = it }
                    )
                }

                if (startTime.isNotEmpty() || endTime.isNotEmpty()) {
                    TextButton(onClick = {
                        startTime = ""
                        endTime = ""
                    }) { Text("Zeiten zurücksetzen (ganztägig)") }
                }

                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Notiz (z. B. Rufbereitschaft)") },
                    modifier = Modifier.fillMaxWidth()
                )

                TextButton(
                    onClick = { showConfirmDelete = true },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Bereitschaft löschen", color = ColorNegative)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                onSave(
                    entry.copy(
                        date = startDate,
                        endDate = endDate,
                        start = startTime.ifEmpty { null },
                        end = endTime.ifEmpty { null },
                        note = note.ifBlank { null }
                    )
                )
            }) { Text("Speichern") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Abbrechen") }
        }
    )

    if (showConfirmDelete) {
        AlertDialog(
            onDismissRequest = { showConfirmDelete = false },
            title = { Text("Bereitschaft löschen?") },
            text = { Text("Dieser Bereitschaftseintrag wird gelöscht.") },
            confirmButton = {
                TextButton(onClick = {
                    showConfirmDelete = false
                    onDelete()
                }) { Text("Löschen", color = ColorNegative) }
            },
            dismissButton = {
                TextButton(onClick = { showConfirmDelete = false }) { Text("Abbrechen") }
            }
        )
    }
}

@Composable
private fun LabeledRow(label: String, value: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
            .padding(12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text("$label:")
        Text(value, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun TimePickerBox(
    modifier: Modifier = Modifier,
    label: String,
    value: String,
    onPicked: (String) -> Unit
) {
    val context = LocalContext.current
    Box(
        modifier = modifier
            .clickable {
                val t = runCatching { LocalTime.parse(value) }.getOrDefault(LocalTime.of(8, 0))
                TimePickerDialog(
                    context,
                    { _, h, m -> onPicked(String.format(Locale.ROOT, "%02d:%02d", h, m)) },
                    t.hour, t.minute, true
                ).show()
            }
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
            .padding(12.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, fontSize = 11.sp)
            Text(value, fontWeight = FontWeight.Bold)
        }
    }
}

private val DAY_FORMATTER: DateTimeFormatter = DateTimeFormatter.ofPattern("EEEE, dd.MM.yyyy", Locale.GERMAN)

@Composable
fun DayDetailsDialog(
    date: LocalDate,
    targetMinutes: Int,
    entries: List<WorkEntryEntity>,
    bereitschaft: List<BereitschaftEntryEntity>,
    holidayName: String?,
    onDismiss: () -> Unit
) {
    val dayBalance = entries.sumOf { it.minutes }
    val saldoColor = when {
        dayBalance > 0 -> ColorPositive
        dayBalance < 0 -> ColorNegative
        else -> MaterialTheme.colorScheme.onSurface
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column {
                Text(date.format(DAY_FORMATTER), fontWeight = FontWeight.Bold, fontSize = 16.sp)
                if (!holidayName.isNullOrEmpty()) {
                    Text(holidayName, fontSize = 12.sp, color = ColorInfo, fontWeight = FontWeight.Medium)
                }
            }
        },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("Tages-Saldo:", fontWeight = FontWeight.Bold)
                    Text(
                        TimeCalculator.formatMinutes(dayBalance, showPlus = true),
                        fontWeight = FontWeight.Black,
                        color = saldoColor,
                        fontSize = 18.sp
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("Tagessoll:", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(formatHm(targetMinutes), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }

                if (entries.isEmpty() && bereitschaft.isEmpty()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text("Keine Einträge", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }

                if (entries.isNotEmpty()) {
                    Divider()
                    Text("Einträge", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    for (e in entries.sortedBy { it.start ?: "" }) {
                        EntryRow(e)
                    }
                }
                if (bereitschaft.isNotEmpty()) {
                    Divider()
                    Text("Bereitschaft", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    for (b in bereitschaft) {
                        val span = listOfNotNull(b.start.takeUnless { it.isNullOrEmpty() }, b.end.takeUnless { it.isNullOrEmpty() })
                            .joinToString(" – ")
                            .ifEmpty { "ganztägig" }
                        Text(
                            buildString {
                                append(span)
                                if (!b.note.isNullOrEmpty()) {
                                    append("  · ")
                                    append(b.note)
                                }
                            },
                            fontSize = 12.sp,
                            color = ColorInfo
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Schließen") }
        }
    )
}

@Composable
private fun EntryRow(e: WorkEntryEntity) {
    val timeLabel = when {
        !e.start.isNullOrEmpty() && !e.end.isNullOrEmpty() -> "${e.start} – ${e.end}"
        else -> "Manuell"
    }
    val deltaColor = when {
        e.minutes > 0 -> ColorPositive
        e.minutes < 0 -> ColorNegative
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(timeLabel, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            Text(
                TimeCalculator.formatMinutes(e.minutes, showPlus = true),
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = deltaColor
            )
        }
        val extras = buildList {
            if (e.pause > 0) add("Pause ${e.pause}m")
            if (!e.reason.isNullOrEmpty()) add(e.reason)
        }
        if (extras.isNotEmpty()) {
            Text(
                extras.joinToString(" · "),
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

private fun formatHm(minutes: Int): String {
    val h = minutes / 60
    val m = minutes % 60
    return "${h}h ${m}m"
}

private val SHORT_DATE_FMT: DateTimeFormatter =
    DateTimeFormatter.ofPattern("dd.MM.yyyy", Locale.GERMAN)

private fun formatDateDe(isoDate: String): String =
    runCatching { LocalDate.parse(isoDate).format(SHORT_DATE_FMT) }.getOrDefault(isoDate)
