package de.bluelight.ueberzeitrechner.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.bluelight.ueberzeitrechner.data.BereitschaftEntryEntity
import de.bluelight.ueberzeitrechner.data.WorkEntryEntity
import de.bluelight.ueberzeitrechner.logic.HolidayManager
import de.bluelight.ueberzeitrechner.ui.theme.ColorInfo
import de.bluelight.ueberzeitrechner.ui.theme.ColorNegative
import de.bluelight.ueberzeitrechner.ui.theme.ColorPositive
import de.bluelight.ueberzeitrechner.viewmodel.MainViewModel
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CalendarScreen(viewModel: MainViewModel) {
    val entries by viewModel.entries.collectAsState()
    val bereitschaft by viewModel.bereitschaft.collectAsState()
    val stateCode by viewModel.stateCode.collectAsState()

    var currentMonth by remember { mutableStateOf(YearMonth.now()) }
    var selectedDate by remember { mutableStateOf<LocalDate?>(null) }

    val daysInMonth = currentMonth.lengthOfMonth()
    val firstDayOfMonth = currentMonth.atDay(1)
    val dayOfWeekOffset = firstDayOfMonth.dayOfWeek.value - 1 // 0 for Mon, 6 for Sun

    val holidays = remember(currentMonth, stateCode) {
        HolidayManager.getGermanHolidays(currentMonth.year, stateCode)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Kalender-Heatmap", fontWeight = FontWeight.Bold) }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // --- Month Navigation Row ---
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = { currentMonth = currentMonth.minusMonths(1) }) {
                    Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Vorheriger Monat")
                }
                Text(
                    text = "${currentMonth.month.getDisplayName(TextStyle.FULL, Locale.GERMAN)} ${currentMonth.year}",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                IconButton(onClick = { currentMonth = currentMonth.plusMonths(1) }) {
                    Icon(Icons.Default.KeyboardArrowRight, contentDescription = "Nächster Monat")
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // --- Weekdays Header ---
            Row(modifier = Modifier.fillMaxWidth()) {
                val weekdays = listOf("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
                weekdays.forEach { day ->
                    Text(
                        text = day,
                        modifier = Modifier.weight(1f),
                        textAlign = TextAlign.Center,
                        fontWeight = FontWeight.Bold,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // --- Calendar Grid ---
            val totalCells = daysInMonth + dayOfWeekOffset
            val rows = if (totalCells % 7 == 0) totalCells / 7 else (totalCells / 7) + 1

            LazyVerticalGrid(
                columns = GridCells.Fixed(7),
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Empty spacer items before day 1
                items(dayOfWeekOffset) {
                    Box(modifier = Modifier.aspectRatio(1f))
                }

                // Days
                items(daysInMonth) { index ->
                    val dayNum = index + 1
                    val date = currentMonth.atDay(dayNum)
                    val dateStr = date.toString()

                    val dayEntries = entries.filter { it.date == dateStr }
                    val dayBereitschaft = bereitschaft.filter { b ->
                        val startD = runCatching { LocalDate.parse(b.date) }.getOrNull()
                            ?: return@filter false
                        val endD = runCatching { LocalDate.parse(b.endDate ?: b.date) }.getOrNull()
                            ?: startD
                        !date.isBefore(startD) && !date.isAfter(endD)
                    }

                    CalendarDayCell(
                        date = date,
                        entries = dayEntries,
                        bereitschaft = dayBereitschaft,
                        holidayName = holidays[dateStr],
                        onClick = { selectedDate = date }
                    )
                }
            }
        }
    }

    selectedDate?.let { d ->
        val dStr = d.toString()
        val dayEntries = entries.filter { it.date == dStr }
        val dayBereitschaft = bereitschaft.filter { b ->
            val s = runCatching { LocalDate.parse(b.date) }.getOrNull() ?: return@filter false
            val e = runCatching { LocalDate.parse(b.endDate ?: b.date) }.getOrNull() ?: s
            !d.isBefore(s) && !d.isAfter(e)
        }
        val customTarget = dayEntries.firstOrNull { it.targetMinutes != -1 }?.targetMinutes ?: -1
        val target = viewModel.getTargetMinutesForDate(dStr, customTarget)
        DayDetailsDialog(
            date = d,
            targetMinutes = target,
            entries = dayEntries,
            bereitschaft = dayBereitschaft,
            holidayName = holidays[dStr],
            onDismiss = { selectedDate = null }
        )
    }
}

@Composable
fun CalendarDayCell(
    date: LocalDate,
    entries: List<WorkEntryEntity>,
    bereitschaft: List<BereitschaftEntryEntity>,
    holidayName: String?,
    onClick: () -> Unit
) {
    // Day saldo follows desktop semantics: sum of per-entry overtime deltas. The
    // ViewModel keeps `minutes` in that shape via recalculateDay() after every change.
    val balance = entries.sumOf { it.minutes }

    val hasEntries = entries.isNotEmpty()
    val isHoliday = holidayName != null

    val backgroundColor = when {
        hasEntries -> when {
            balance > 0 -> ColorPositive.copy(alpha = 0.18f)
            balance < 0 -> ColorNegative.copy(alpha = 0.18f)
            else -> MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
        }
        isHoliday -> ColorInfo.copy(alpha = 0.10f)
        date.dayOfWeek.value in 6..7 -> MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f)
        else -> MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.2f)
    }

    val textColor = when {
        hasEntries -> when {
            balance > 0 -> ColorPositive
            balance < 0 -> ColorNegative
            else -> MaterialTheme.colorScheme.onSurface
        }
        isHoliday -> ColorInfo
        else -> MaterialTheme.colorScheme.onSurface
    }

    Box(
        modifier = Modifier
            .aspectRatio(1f)
            .clip(RoundedCornerShape(8.dp))
            .background(backgroundColor)
            .clickable(onClick = onClick)
            .padding(4.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween,
            modifier = Modifier.fillMaxSize()
        ) {
            // Holiday indicator
            if (isHoliday) {
                Box(
                    modifier = Modifier
                        .size(4.dp)
                        .clip(CircleShape)
                        .background(ColorInfo)
                )
            } else {
                Spacer(modifier = Modifier.height(4.dp))
            }

            // Day Number
            Text(
                text = date.dayOfMonth.toString(),
                fontWeight = if (hasEntries || isHoliday) FontWeight.Bold else FontWeight.Normal,
                color = textColor,
                fontSize = 14.sp
            )

            // Standby (Bereitschaft) Marker: Continuous bottom bar matching desktop style
            if (bereitschaft.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(3.dp)
                        .clip(RoundedCornerShape(1.dp))
                        .background(ColorInfo)
                )
            } else {
                Spacer(modifier = Modifier.height(3.dp))
            }
        }
    }
}
