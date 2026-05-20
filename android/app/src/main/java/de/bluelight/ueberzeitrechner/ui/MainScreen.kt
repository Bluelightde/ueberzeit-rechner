package de.bluelight.ueberzeitrechner.ui

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.bluelight.ueberzeitrechner.data.WorkEntryEntity
import de.bluelight.ueberzeitrechner.logic.TimeCalculator
import de.bluelight.ueberzeitrechner.ui.theme.ColorNegative
import de.bluelight.ueberzeitrechner.ui.theme.ColorPositive
import de.bluelight.ueberzeitrechner.viewmodel.MainViewModel
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.Calendar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(viewModel: MainViewModel) {
    val context = LocalContext.current
    val entries by viewModel.entries.collectAsState()
    val overallBalance by viewModel.overallBalance.collectAsState()
    val autoBreak by viewModel.autoBreak.collectAsState()

    var showForm by remember { mutableStateOf(false) }

    // --- Form States ---
    var isManualEntry by remember { mutableStateOf(false) }
    var date by remember { mutableStateOf(LocalDate.now().toString()) }
    var startTime by remember { mutableStateOf("08:00") }
    var endTime by remember { mutableStateOf("16:30") }
    var pauseMins by remember { mutableStateOf("0") }
    var manualMinutesText by remember { mutableStateOf("") }
    var manualSignPositive by remember { mutableStateOf(true) }
    var reason by remember { mutableStateOf("") }
    var hasCustomTarget by remember { mutableStateOf(false) }
    var customTargetTime by remember { mutableStateOf("08:00") }

    Scaffold(
        topBar = {
            LargeTopAppBar(
                title = {
                    Text(
                        "Überzeit Rechner",
                        fontWeight = FontWeight.Bold
                    )
                },
                colors = TopAppBarDefaults.largeTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        floatingActionButton = {
            // Hide the FAB while the form is open — otherwise it covers the submit
            // button on the right and the user can tap the FAB by mistake.
            if (!showForm) {
                ExtendedFloatingActionButton(
                    onClick = { showForm = true },
                    icon = { Icon(Icons.Default.Add, "Erfassen") },
                    text = { Text("Erfassen") }
                )
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
        ) {
            // --- Overall Balance Banner ---
            val isPositive = overallBalance >= 0
            val bannerColor = if (isPositive) ColorPositive else ColorNegative
            
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(bannerColor)
                    .padding(24.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = "GESAMT-SALDO",
                        color = Color.White,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.5.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = TimeCalculator.formatMinutes(overallBalance, showPlus = true),
                        color = Color.White,
                        fontSize = 32.sp,
                        fontWeight = FontWeight.Black
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // --- Expandable Quick Add Form ---
            AnimatedVisibility(visible = showForm) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            if (isManualEntry) "Manueller Eintrag" else "Arbeitszeit erfassen",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )

                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = isManualEntry,
                                onCheckedChange = { isManualEntry = it }
                            )
                            Column {
                                Text("Manueller Eintrag (Plus/Minus-Minuten)", fontSize = 13.sp)
                                Text(
                                    "Für Dienstreisen, Comp-Time, früher Schluss …",
                                    fontSize = 11.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }

                        // Date Picker
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    val calendar = Calendar.getInstance()
                                    DatePickerDialog(
                                        context,
                                        { _, y, m, d ->
                                            date = LocalDate.of(y, m + 1, d).toString()
                                        },
                                        calendar.get(Calendar.YEAR),
                                        calendar.get(Calendar.MONTH),
                                        calendar.get(Calendar.DAY_OF_MONTH)
                                    ).show()
                                }
                                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Datum:")
                            Text(date, fontWeight = FontWeight.Bold)
                        }

                        if (!isManualEntry) {
                            // Time pickers
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Box(
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable {
                                            val t = LocalTime.parse(startTime)
                                            TimePickerDialog(context, { _, h, m ->
                                                startTime = String.format("%02d:%02d", h, m)
                                            }, t.hour, t.minute, true).show()
                                        }
                                        .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                        .padding(12.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text("Startzeit", fontSize = 11.sp)
                                        Text(startTime, fontWeight = FontWeight.Bold)
                                    }
                                }

                                Box(
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable {
                                            val t = LocalTime.parse(endTime)
                                            TimePickerDialog(context, { _, h, m ->
                                                endTime = String.format("%02d:%02d", h, m)
                                            }, t.hour, t.minute, true).show()
                                        }
                                        .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                        .padding(12.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text("Endzeit", fontSize = 11.sp)
                                        Text(endTime, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }

                            // Break / Pause
                            if (!autoBreak) {
                                OutlinedTextField(
                                    value = pauseMins,
                                    onValueChange = { input -> pauseMins = input.filter(Char::isDigit) },
                                    label = { Text("Pause (in Min.)") },
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        } else {
                            // Manual minutes: signed minute delta (positive = overtime).
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                FilterChip(
                                    selected = manualSignPositive,
                                    onClick = { manualSignPositive = true },
                                    label = { Text("+ Plus") },
                                    leadingIcon = if (manualSignPositive) {
                                        { Icon(Icons.Default.Add, contentDescription = null) }
                                    } else null
                                )
                                FilterChip(
                                    selected = !manualSignPositive,
                                    onClick = { manualSignPositive = false },
                                    label = { Text("− Minus") }
                                )
                            }
                            OutlinedTextField(
                                value = manualMinutesText,
                                onValueChange = { input -> manualMinutesText = input.filter(Char::isDigit).take(5) },
                                label = { Text("Minuten") },
                                placeholder = { Text("z. B. 60") },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                modifier = Modifier.fillMaxWidth()
                            )
                            val previewMins = manualMinutesText.toIntOrNull() ?: 0
                            val signedPreview = if (manualSignPositive) previewMins else -previewMins
                            if (previewMins > 0) {
                                Text(
                                    "Wird als ${if (signedPreview >= 0) "+" else ""}${signedPreview / 60}h ${kotlin.math.abs(signedPreview) % 60}m gespeichert.",
                                    fontSize = 11.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }

                        // Reason
                        OutlinedTextField(
                            value = reason,
                            onValueChange = { reason = it },
                            label = { Text("Notiz / Tätigkeit (optional)") },
                            modifier = Modifier.fillMaxWidth()
                        )

                        // Custom Target Override
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Checkbox(checked = hasCustomTarget, onCheckedChange = { hasCustomTarget = it })
                            Text("Individuelles Tagessoll", fontSize = 14.sp)
                        }

                        if (hasCustomTarget) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        val t = LocalTime.parse(customTargetTime)
                                        TimePickerDialog(context, { _, h, m ->
                                            customTargetTime = String.format("%02d:%02d", h, m)
                                        }, t.hour, t.minute, true).show()
                                    }
                                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                    .padding(12.dp),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Indiv. Soll:")
                                Text(customTargetTime, fontWeight = FontWeight.Bold)
                            }
                        }

                        // Submit / Cancel
                        val canSubmit = !isManualEntry || (manualMinutesText.toIntOrNull() ?: 0) > 0
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            OutlinedButton(
                                onClick = {
                                    showForm = false
                                    reason = ""
                                    manualMinutesText = ""
                                    manualSignPositive = true
                                },
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)
                            ) {
                                Text("Abbrechen", maxLines = 1)
                            }
                            Button(
                                onClick = {
                                    val targetMins = if (hasCustomTarget) {
                                        val t = LocalTime.parse(customTargetTime)
                                        t.hour * 60 + t.minute
                                    } else -1

                                    if (isManualEntry) {
                                        val raw = manualMinutesText.toIntOrNull() ?: 0
                                        val signed = if (manualSignPositive) raw else -raw
                                        viewModel.addManualEntry(
                                            date = date,
                                            minutes = signed,
                                            reason = reason.ifBlank { null },
                                            target = targetMins
                                        )
                                    } else {
                                        val pauseVal = pauseMins.toIntOrNull() ?: 0
                                        viewModel.addWorkEntry(
                                            date = date,
                                            start = startTime,
                                            end = endTime,
                                            pause = pauseVal,
                                            reason = reason.ifBlank { null },
                                            target = targetMins
                                        )
                                    }
                                    showForm = false
                                    reason = ""
                                    manualMinutesText = ""
                                    manualSignPositive = true
                                },
                                modifier = Modifier.weight(2f),
                                enabled = canSubmit,
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)
                            ) {
                                Text("Hinzufügen", maxLines = 1)
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // --- Entries List ---
            Text("Vergangene Tage", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(8.dp))

            var editing by remember { mutableStateOf<WorkEntryEntity?>(null) }

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.weight(1f)
            ) {
                items(entries) { entry ->
                    WorkEntryItem(entry, onClick = { editing = entry })
                }
            }

            editing?.let { current ->
                EditEntryDialog(
                    entry = current,
                    autoBreak = autoBreak,
                    onSave = { updated ->
                        viewModel.updateWorkEntry(updated)
                        editing = null
                    },
                    onDelete = {
                        viewModel.deleteWorkEntry(current.id)
                        editing = null
                    },
                    onDismiss = { editing = null }
                )
            }
        }
    }
}

@Composable
fun WorkEntryItem(entry: WorkEntryEntity, onClick: () -> Unit) {
    val saldoColor = when {
        entry.minutes > 0 -> ColorPositive
        entry.minutes < 0 -> ColorNegative
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = entry.date,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
                val timeLabel = when {
                    !entry.start.isNullOrEmpty() && !entry.end.isNullOrEmpty() ->
                        "${entry.start} – ${entry.end}" +
                            (if (entry.pause > 0) " (Pause: ${entry.pause}m)" else "")
                    else -> "Manueller Eintrag"
                }
                Text(
                    text = timeLabel,
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (!entry.reason.isNullOrEmpty()) {
                    Text(
                        text = entry.reason,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontWeight = FontWeight.Medium
                    )
                }
            }

            Text(
                text = TimeCalculator.formatMinutes(entry.minutes, showPlus = true),
                color = saldoColor,
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp
            )
        }
    }
}
