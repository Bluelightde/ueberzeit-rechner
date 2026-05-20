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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.bluelight.ueberzeitrechner.data.BereitschaftEntryEntity
import de.bluelight.ueberzeitrechner.ui.theme.ColorInfo
import de.bluelight.ueberzeitrechner.ui.theme.ColorNegative
import de.bluelight.ueberzeitrechner.viewmodel.MainViewModel
import java.time.LocalDate
import java.time.LocalTime
import java.util.Calendar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BereitschaftScreen(viewModel: MainViewModel) {
    val context = LocalContext.current
    val standbyEntries by viewModel.bereitschaft.collectAsState()

    var showForm by remember { mutableStateOf(false) }

    // --- Form States ---
    var startDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var endDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var startTime by remember { mutableStateOf("") }
    var endTime by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Bereitschafts-Erfassung", fontWeight = FontWeight.Bold) }
            )
        },
        floatingActionButton = {
            if (!showForm) {
                ExtendedFloatingActionButton(
                    onClick = { showForm = true },
                    icon = { Icon(Icons.Default.Add, "Bereitschaft eintragen") },
                    text = { Text("Bereitschaft eintragen") }
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
            // Description Banner
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(
                    containerColor = ColorInfo.copy(alpha = 0.12f)
                )
            ) {
                Text(
                    text = "Bereitschaftszeiten werden im Kalender als blaue Linie markiert. Sie haben keinen Einfluss auf deine regulären Überstunden.",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Expandable form
            AnimatedVisibility(visible = showForm) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text("Bereitschaft hinzufügen", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)

                        // Start date
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    val c = Calendar.getInstance()
                                    DatePickerDialog(context, { _, y, m, d ->
                                        startDate = LocalDate.of(y, m + 1, d).toString()
                                        if (LocalDate.parse(endDate).isBefore(LocalDate.of(y, m + 1, d))) {
                                            endDate = startDate
                                        }
                                    }, c.get(Calendar.YEAR), c.get(Calendar.MONTH), c.get(Calendar.DAY_OF_MONTH)).show()
                                }
                                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Start-Datum:")
                            Text(startDate, fontWeight = FontWeight.Bold)
                        }

                        // End date
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    val c = Calendar.getInstance()
                                    DatePickerDialog(context, { _, y, m, d ->
                                        endDate = LocalDate.of(y, m + 1, d).toString()
                                    }, c.get(Calendar.YEAR), c.get(Calendar.MONTH), c.get(Calendar.DAY_OF_MONTH)).show()
                                }
                                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("End-Datum:")
                            Text(endDate, fontWeight = FontWeight.Bold)
                        }

                        // Optional times
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable {
                                        val now = LocalTime.now()
                                        TimePickerDialog(context, { _, h, m ->
                                            startTime = String.format("%02d:%02d", h, m)
                                        }, now.hour, now.minute, true).show()
                                    }
                                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                    .padding(12.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text("Startzeit (opt)", fontSize = 11.sp)
                                    Text(if (startTime.isEmpty()) "--:--" else startTime, fontWeight = FontWeight.Bold)
                                }
                            }

                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable {
                                        val now = LocalTime.now()
                                        TimePickerDialog(context, { _, h, m ->
                                            endTime = String.format("%02d:%02d", h, m)
                                        }, now.hour, now.minute, true).show()
                                    }
                                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                                    .padding(12.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text("Endzeit (opt)", fontSize = 11.sp)
                                    Text(if (endTime.isEmpty()) "--:--" else endTime, fontWeight = FontWeight.Bold)
                                }
                            }
                        }

                        // Note / Description
                        OutlinedTextField(
                            value = note,
                            onValueChange = { note = it },
                            label = { Text("Notiz (z. B. Rufbereitschaft)") },
                            modifier = Modifier.fillMaxWidth()
                        )

                        // Submit / Cancel
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            OutlinedButton(
                                onClick = {
                                    showForm = false
                                    note = ""
                                    startTime = ""
                                    endTime = ""
                                },
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)
                            ) {
                                Text("Abbrechen", maxLines = 1)
                            }
                            Button(
                                onClick = {
                                    viewModel.addBereitschaft(
                                        date = startDate,
                                        endDate = endDate,
                                        start = startTime.ifEmpty { null },
                                        end = endTime.ifEmpty { null },
                                        note = note
                                    )
                                    showForm = false
                                    note = ""
                                    startTime = ""
                                    endTime = ""
                                },
                                modifier = Modifier.weight(2f),
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)
                            ) {
                                Text("Hinzufügen", maxLines = 1)
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Entries List
            Text("Bereitschaftszeiten", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(8.dp))

            var editing by remember { mutableStateOf<BereitschaftEntryEntity?>(null) }

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.weight(1f)
            ) {
                items(standbyEntries) { entry ->
                    StandbyEntryItem(entry, onClick = { editing = entry })
                }
            }

            editing?.let { current ->
                EditBereitschaftDialog(
                    entry = current,
                    onSave = { updated ->
                        viewModel.updateBereitschaft(updated)
                        editing = null
                    },
                    onDelete = {
                        viewModel.deleteBereitschaft(current.id)
                        editing = null
                    },
                    onDismiss = { editing = null }
                )
            }
        }
    }
}

@Composable
fun StandbyEntryItem(entry: BereitschaftEntryEntity, onClick: () -> Unit) {
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
                val dateLabel = if (entry.date == entry.endDate || entry.endDate.isNullOrEmpty()) {
                    entry.date
                } else {
                    "${entry.date} bis ${entry.endDate}"
                }
                Text(
                    text = dateLabel,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp
                )
                if (!entry.start.isNullOrEmpty() && !entry.end.isNullOrEmpty()) {
                    Text(
                        text = "${entry.start} - ${entry.end}",
                        fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                if (!entry.note.isNullOrEmpty()) {
                    Text(
                        text = entry.note,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium,
                        color = ColorInfo
                    )
                }
            }
        }
    }
}
