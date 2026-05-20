package de.bluelight.ueberzeitrechner.ui

import android.app.TimePickerDialog
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.bluelight.ueberzeitrechner.ui.theme.ColorInfo
import de.bluelight.ueberzeitrechner.ui.theme.ColorNegative
import de.bluelight.ueberzeitrechner.ui.theme.ColorPositive
import de.bluelight.ueberzeitrechner.viewmodel.ImportStatus
import de.bluelight.ueberzeitrechner.viewmodel.MainViewModel
import de.bluelight.ueberzeitrechner.viewmodel.SyncStatus
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private class OpenDocumentRW : ActivityResultContracts.OpenDocument() {
    override fun createIntent(context: Context, input: Array<String>): Intent {
        return super.createIntent(context, input).apply {
            addFlags(
                Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION or
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(viewModel: MainViewModel) {
    val context = LocalContext.current

    val targetMins by viewModel.targetWorkTime.collectAsState()
    val autoBreak by viewModel.autoBreak.collectAsState()
    val country by viewModel.country.collectAsState()
    val stateCode by viewModel.stateCode.collectAsState()
    val importStatus by viewModel.importStatus.collectAsState()
    val syncStatus by viewModel.syncStatus.collectAsState()
    val linkedLabel by viewModel.linkedUriLabel.collectAsState()

    var showStateMenu by remember { mutableStateOf(false) }

    val states = listOf(
        "BW" to "Baden-Württemberg",
        "BY" to "Bayern",
        "BE" to "Berlin",
        "BB" to "Brandenburg",
        "HB" to "Bremen",
        "HH" to "Hamburg",
        "HE" to "Hessen",
        "MV" to "Mecklenburg-Vorpommern",
        "NI" to "Niedersachsen",
        "NW" to "Nordrhein-Westfalen",
        "RP" to "Rheinland-Pfalz",
        "SL" to "Saarland",
        "SN" to "Sachsen",
        "ST" to "Sachsen-Anhalt",
        "SH" to "Schleswig-Holstein",
        "TH" to "Thüringen"
    )

    val dbPickerLauncher = rememberLauncherForActivityResult(
        contract = OpenDocumentRW(),
        onResult = { uri: Uri? ->
            uri?.let { viewModel.importExternalDatabase(context, it) }
        }
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Einstellungen & Sync", fontWeight = FontWeight.Bold) }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text("Arbeitszeit & Gesetzgebung", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        val h = targetMins / 60
                        val m = targetMins % 60
                        TimePickerDialog(context, { _, selectedH, selectedM ->
                            viewModel.updateTargetWorkTime(selectedH * 60 + selectedM)
                        }, h, m, true).show()
                    }
                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Standard-Tagessoll:")
                Text("${targetMins / 60}h ${targetMins % 60}m", fontWeight = FontWeight.Bold)
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Automatische Pause (ArbZG)")
                    Text(
                        "Zieht gesetzliche Pausen automatisch ab (>6h = 30m, >9h = 45m)",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Switch(checked = autoBreak, onCheckedChange = { viewModel.updateAutoBreak(it) })
            }

            Divider()

            Text("Region & Feiertage", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)

            Box(modifier = Modifier.fillMaxWidth()) {
                val stateName = states.firstOrNull { it.first == stateCode }?.second ?: stateCode
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { showStateMenu = true }
                        .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Bundesland:")
                    Text(stateName, fontWeight = FontWeight.Bold)
                }

                DropdownMenu(expanded = showStateMenu, onDismissRequest = { showStateMenu = false }) {
                    states.forEach { (code, name) ->
                        DropdownMenuItem(
                            text = { Text(name) },
                            onClick = {
                                viewModel.updateRegion(country, code)
                                showStateMenu = false
                            }
                        )
                    }
                }
            }

            Divider()

            Text("Datenbank-Sync", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = ColorInfo.copy(alpha = 0.12f))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Verknüpfte Datei", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(linkedLabel ?: "Keine — Änderungen bleiben lokal in der App.", fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.height(8.dp))
                    SyncStatusLine(syncStatus)
                }
            }

            val isImporting = importStatus is ImportStatus.InProgress
            val isExporting = syncStatus is SyncStatus.InProgress

            Button(
                onClick = { dbPickerLauncher.launch(arrayOf("application/octet-stream", "application/x-sqlite3", "*/*")) },
                modifier = Modifier.fillMaxWidth(),
                enabled = !isImporting && !isExporting
            ) {
                Text(if (isImporting) "Importiere…" else "Datenbank importieren / verknüpfen")
            }

            if (linkedLabel != null) {
                OutlinedButton(
                    onClick = { viewModel.manualExport() },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !isImporting && !isExporting
                ) {
                    Text(if (isExporting) "Speichere…" else "Jetzt zur Datei speichern")
                }
                TextButton(
                    onClick = { viewModel.unlinkSourceFile() },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Verknüpfung lösen (lokal bleiben)")
                }
            }

            when (val status = importStatus) {
                is ImportStatus.Success -> {
                    StatusCard(
                        title = "Import erfolgreich",
                        body = "${status.workEntries} Arbeitseinträge, ${status.bereitschaftEntries} Bereitschaftseinträge übernommen.",
                        container = ColorPositive.copy(alpha = 0.18f),
                        onDismiss = { viewModel.acknowledgeImportStatus() }
                    )
                }
                is ImportStatus.Error -> {
                    StatusCard(
                        title = "Import fehlgeschlagen",
                        body = status.message,
                        container = MaterialTheme.colorScheme.errorContainer,
                        onDismiss = { viewModel.acknowledgeImportStatus() }
                    )
                }
                else -> {}
            }
        }
    }
}

@Composable
private fun SyncStatusLine(status: SyncStatus) {
    val (label, color) = when (status) {
        SyncStatus.NotLinked -> "Nicht verknüpft" to MaterialTheme.colorScheme.onSurfaceVariant
        SyncStatus.Idle -> "Noch nicht gespeichert" to MaterialTheme.colorScheme.onSurfaceVariant
        SyncStatus.InProgress -> "Speichere…" to MaterialTheme.colorScheme.onSurface
        is SyncStatus.Success -> "Zuletzt gespeichert: ${formatTime(status.timestampMs)}" to ColorPositive
        is SyncStatus.Error -> "Fehler: ${status.message}" to ColorNegative
    }
    Text(label, fontSize = 12.sp, color = color, fontWeight = FontWeight.Medium)
}

@Composable
private fun StatusCard(title: String, body: String, container: androidx.compose.ui.graphics.Color, onDismiss: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onDismiss),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = container)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            Spacer(modifier = Modifier.height(4.dp))
            Text(body, fontSize = 12.sp)
        }
    }
}

private val TIME_FMT = SimpleDateFormat("dd.MM. HH:mm", Locale.GERMAN)

private fun formatTime(ms: Long): String = TIME_FMT.format(Date(ms))
