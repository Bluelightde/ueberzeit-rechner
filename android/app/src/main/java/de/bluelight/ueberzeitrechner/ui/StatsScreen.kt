package de.bluelight.ueberzeitrechner.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.bluelight.ueberzeitrechner.logic.TimeCalculator
import de.bluelight.ueberzeitrechner.ui.theme.ColorNegative
import de.bluelight.ueberzeitrechner.ui.theme.ColorPositive
import de.bluelight.ueberzeitrechner.viewmodel.MainViewModel
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.pow

private val MONTHS_DE = arrayOf(
    "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"
)

private fun shortMonthLabel(yyyymm: String): String {
    if (yyyymm.length < 7) return yyyymm
    val year = yyyymm.substring(2, 4)
    val month = yyyymm.substring(5, 7).toIntOrNull() ?: return yyyymm
    return "${MONTHS_DE[month - 1]} $year"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatsScreen(viewModel: MainViewModel) {
    val entries by viewModel.entries.collectAsState()
    val overallBalance by viewModel.overallBalance.collectAsState()

    val scrollState = rememberScrollState()

    // Aggregated views derived once per entry-list change. All values follow the
    // desktop semantics where `minutes` is already the per-entry overtime delta.
    val dailySaldoMinutes: Map<String, Int> = remember(entries) {
        entries.groupBy { it.date }.mapValues { (_, list) -> list.sumOf { it.minutes } }
    }
    val monthlyDeltaMinutes: Map<String, Int> = remember(entries) {
        entries.filter { it.date.length >= 7 }
            .groupBy { it.date.substring(0, 7) }
            .mapValues { (_, list) -> list.sumOf { it.minutes } }
    }
    val monthlyCloseMinutes: Map<String, Int> = remember(entries) {
        val sortedDates = dailySaldoMinutes.keys.sorted()
        var cum = 0
        val result = linkedMapOf<String, Int>()
        for (d in sortedDates) {
            cum += dailySaldoMinutes[d] ?: 0
            if (d.length >= 7) result[d.substring(0, 7)] = cum
        }
        result
    }

    val avgPerMonth: Int = remember(monthlyDeltaMinutes) {
        if (monthlyDeltaMinutes.isEmpty()) 0
        else monthlyDeltaMinutes.values.sum() / monthlyDeltaMinutes.size
    }
    val bestMonth = remember(monthlyDeltaMinutes) {
        monthlyDeltaMinutes.maxByOrNull { it.value }
    }
    val worstMonth = remember(monthlyDeltaMinutes) {
        monthlyDeltaMinutes.minByOrNull { it.value }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Statistiken & Trends", fontWeight = FontWeight.Bold) })
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(scrollState)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                KPICard(
                    title = "Gesamt-Saldo",
                    value = TimeCalculator.formatMinutes(overallBalance, showPlus = true),
                    color = signColor(overallBalance),
                    modifier = Modifier.weight(1f)
                )
                KPICard(
                    title = "ø pro Monat",
                    value = TimeCalculator.formatMinutes(avgPerMonth, showPlus = true),
                    color = signColor(avgPerMonth),
                    modifier = Modifier.weight(1f)
                )
            }

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                KPICard(
                    title = "Bester Monat",
                    value = bestMonth?.let {
                        TimeCalculator.formatMinutes(it.value, showPlus = true) +
                                "\n" + shortMonthLabel(it.key)
                    } ?: "–",
                    color = bestMonth?.let { signColor(it.value) } ?: MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f)
                )
                KPICard(
                    title = "Schlechtester Monat",
                    value = worstMonth?.let {
                        TimeCalculator.formatMinutes(it.value, showPlus = true) +
                                "\n" + shortMonthLabel(it.key)
                    } ?: "–",
                    color = worstMonth?.let { signColor(it.value) } ?: MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f)
                )
            }

            Text(
                "Saldo-Verlauf (Monats-Schlussstand)",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Card(modifier = Modifier.fillMaxWidth().height(260.dp), shape = RoundedCornerShape(16.dp)) {
                Box(modifier = Modifier.fillMaxSize().padding(12.dp)) {
                    if (monthlyCloseMinutes.isEmpty()) {
                        Text(
                            "Noch keine Daten verfügbar",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.align(androidx.compose.ui.Alignment.Center)
                        )
                    } else {
                        CumulativeChart(monthlyCloseMinutes)
                    }
                }
            }

            Text(
                "Monatlicher Saldo",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Card(modifier = Modifier.fillMaxWidth().height(260.dp), shape = RoundedCornerShape(16.dp)) {
                Box(modifier = Modifier.fillMaxSize().padding(12.dp)) {
                    if (monthlyDeltaMinutes.isEmpty()) {
                        Text(
                            "Noch keine Daten verfügbar",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.align(androidx.compose.ui.Alignment.Center)
                        )
                    } else {
                        MonthlyBarChart(monthlyDeltaMinutes)
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun signColor(minutes: Int): Color = when {
    minutes > 0 -> ColorPositive
    minutes < 0 -> ColorNegative
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

@Composable
fun KPICard(title: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Card(modifier = modifier, shape = RoundedCornerShape(16.dp)) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(
                title,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(value, fontSize = 18.sp, fontWeight = FontWeight.Black, color = color, lineHeight = 22.sp)
        }
    }
}

// ===================== Cumulative line chart =====================

@Composable
private fun CumulativeChart(monthlyClose: Map<String, Int>) {
    val months = monthlyClose.keys.sorted()
    val valuesHours = months.map { (monthlyClose[it] ?: 0) / 60f }

    val onSurface = MaterialTheme.colorScheme.onSurface
    val gridColor = onSurface.copy(alpha = 0.12f)
    val zeroColor = onSurface.copy(alpha = 0.45f)
    val labelStyle = TextStyle(color = onSurface, fontSize = 10.sp)
    val measurer = rememberTextMeasurer()
    val density = LocalDensity.current

    Canvas(modifier = Modifier.fillMaxSize()) {
        val leftPad = with(density) { 40.dp.toPx() }
        val rightPad = with(density) { 12.dp.toPx() }
        val topPad = with(density) { 8.dp.toPx() }
        val bottomPad = with(density) { 28.dp.toPx() }

        val plotW = size.width - leftPad - rightPad
        val plotH = size.height - topPad - bottomPad
        if (plotW <= 0 || plotH <= 0) return@Canvas

        val (yMin, yMax, ticks) = computeNiceYRange(valuesHours)

        fun yToPx(v: Float): Float = topPad + plotH * (1f - (v - yMin) / (yMax - yMin))
        fun xToPx(i: Int): Float =
            if (months.size == 1) leftPad + plotW / 2f
            else leftPad + plotW * i.toFloat() / (months.size - 1)

        // Grid + Y labels
        for (t in ticks) {
            val y = yToPx(t)
            drawLine(gridColor, Offset(leftPad, y), Offset(size.width - rightPad, y), 1f)
            val label = formatHourTick(t)
            drawAxisLabel(measurer, label, labelStyle, Offset(leftPad - 4f, y), anchorRight = true, verticalCenter = true)
        }

        // Zero line emphasised
        if (yMin < 0 && yMax > 0) {
            val y = yToPx(0f)
            drawLine(zeroColor, Offset(leftPad, y), Offset(size.width - rightPad, y), 1.5f)
        }

        // Line segments coloured by sign of endpoints
        for (i in 0 until months.size - 1) {
            val segColor =
                if (valuesHours[i] >= 0 && valuesHours[i + 1] >= 0) ColorPositive else ColorNegative
            drawLine(
                color = segColor,
                start = Offset(xToPx(i), yToPx(valuesHours[i])),
                end = Offset(xToPx(i + 1), yToPx(valuesHours[i + 1])),
                strokeWidth = with(density) { 2.dp.toPx() }
            )
        }
        // Markers
        for (i in months.indices) {
            val c = if (valuesHours[i] >= 0) ColorPositive else ColorNegative
            drawCircle(c, radius = with(density) { 3.dp.toPx() }, center = Offset(xToPx(i), yToPx(valuesHours[i])))
        }

        // X labels (subsample to avoid overlap)
        val step = maxOf(1, ceil(months.size / 6.0).toInt())
        val xIndicesToLabel = (months.indices step step).toMutableList()
        if (months.size > 1 && xIndicesToLabel.last() != months.size - 1) {
            xIndicesToLabel.add(months.size - 1)
        }
        for (i in xIndicesToLabel) {
            drawAxisLabel(
                measurer = measurer,
                text = shortMonthLabel(months[i]),
                style = labelStyle,
                origin = Offset(xToPx(i), size.height - bottomPad + 4f),
                anchorRight = false,
                verticalCenter = false,
                horizontalCenter = true
            )
        }
    }
}

// ===================== Monthly bar chart =====================

@Composable
private fun MonthlyBarChart(monthlyDelta: Map<String, Int>) {
    val months = monthlyDelta.keys.sorted()
    val valuesHours = months.map { (monthlyDelta[it] ?: 0) / 60f }

    val onSurface = MaterialTheme.colorScheme.onSurface
    val gridColor = onSurface.copy(alpha = 0.12f)
    val zeroColor = onSurface.copy(alpha = 0.45f)
    val labelStyle = TextStyle(color = onSurface, fontSize = 10.sp)
    val measurer = rememberTextMeasurer()
    val density = LocalDensity.current

    Canvas(modifier = Modifier.fillMaxSize()) {
        val leftPad = with(density) { 40.dp.toPx() }
        val rightPad = with(density) { 12.dp.toPx() }
        val topPad = with(density) { 8.dp.toPx() }
        val bottomPad = with(density) { 28.dp.toPx() }

        val plotW = size.width - leftPad - rightPad
        val plotH = size.height - topPad - bottomPad
        if (plotW <= 0 || plotH <= 0) return@Canvas

        val (yMin, yMax, ticks) = computeNiceYRange(valuesHours)

        fun yToPx(v: Float): Float = topPad + plotH * (1f - (v - yMin) / (yMax - yMin))

        // Grid + Y labels
        for (t in ticks) {
            val y = yToPx(t)
            drawLine(gridColor, Offset(leftPad, y), Offset(size.width - rightPad, y), 1f)
            drawAxisLabel(
                measurer = measurer,
                text = formatHourTick(t),
                style = labelStyle,
                origin = Offset(leftPad - 4f, y),
                anchorRight = true,
                verticalCenter = true
            )
        }

        val zeroY = yToPx(0f)
        if (yMin < 0 && yMax > 0) {
            drawLine(zeroColor, Offset(leftPad, zeroY), Offset(size.width - rightPad, zeroY), 1.5f)
        }

        // Bars
        val colSpace = plotW / months.size
        val barW = colSpace * 0.65f
        for (i in months.indices) {
            val v = valuesHours[i]
            val xCenter = leftPad + colSpace * (i + 0.5f)
            val barX = xCenter - barW / 2
            val barTop = if (v >= 0) yToPx(v) else zeroY
            val barBottom = if (v >= 0) zeroY else yToPx(v)
            val color = if (v >= 0) ColorPositive else ColorNegative
            drawRect(
                color = color,
                topLeft = Offset(barX, barTop),
                size = Size(barW, abs(barBottom - barTop).coerceAtLeast(1f))
            )
        }

        // X labels (subsample)
        val step = maxOf(1, ceil(months.size / 6.0).toInt())
        val xIndicesToLabel = (months.indices step step).toMutableList()
        if (months.size > 1 && xIndicesToLabel.last() != months.size - 1) {
            xIndicesToLabel.add(months.size - 1)
        }
        for (i in xIndicesToLabel) {
            val xCenter = leftPad + colSpace * (i + 0.5f)
            drawAxisLabel(
                measurer = measurer,
                text = shortMonthLabel(months[i]),
                style = labelStyle,
                origin = Offset(xCenter, size.height - bottomPad + 4f),
                anchorRight = false,
                verticalCenter = false,
                horizontalCenter = true
            )
        }
    }
}

// ===================== Helpers =====================

private fun DrawScope.drawAxisLabel(
    measurer: TextMeasurer,
    text: String,
    style: TextStyle,
    origin: Offset,
    anchorRight: Boolean = false,
    verticalCenter: Boolean = false,
    horizontalCenter: Boolean = false
) {
    val layout = measurer.measure(text, style)
    val x = when {
        anchorRight -> origin.x - layout.size.width
        horizontalCenter -> origin.x - layout.size.width / 2f
        else -> origin.x
    }
    val y = if (verticalCenter) origin.y - layout.size.height / 2f else origin.y
    drawText(layout, topLeft = Offset(x, y))
}

private fun formatHourTick(hours: Float): String {
    // Whole hours when possible, else 1 decimal
    return if (abs(hours - hours.toInt()) < 0.05f) "${hours.toInt()}h"
    else String.format("%.1fh", hours)
}

private data class NiceRange(val min: Float, val max: Float, val ticks: List<Float>)

/**
 * Picks a Y range and 3–5 tick positions that look like a real chart axis.
 * Always includes zero. Uses 1/2/5×10^n step sizes (matplotlib-style).
 */
private fun computeNiceYRange(values: List<Float>): NiceRange {
    if (values.isEmpty()) return NiceRange(-1f, 1f, listOf(-1f, 0f, 1f))
    val rawMin = minOf(0f, values.min())
    val rawMax = maxOf(0f, values.max())
    val span = (rawMax - rawMin).coerceAtLeast(1f)
    val pad = span * 0.1f
    val paddedMin = rawMin - pad
    val paddedMax = rawMax + pad

    val step = niceStep(paddedMax - paddedMin, 4)
    val niceMin = floor(paddedMin / step) * step
    val niceMax = ceil(paddedMax / step) * step

    val ticks = mutableListOf<Float>()
    var t = niceMin
    while (t <= niceMax + step * 0.001f) {
        ticks.add(t)
        t += step
    }
    return NiceRange(niceMin, niceMax, ticks)
}

private fun niceStep(span: Float, targetTicks: Int): Float {
    val rough = (span / targetTicks).coerceAtLeast(0.0001f)
    val exp = floor(log10(rough.toDouble())).toInt()
    val mag = 10.0.pow(exp.toDouble()).toFloat()
    val normalized = rough / mag
    val niceMult = when {
        normalized < 1.5f -> 1f
        normalized < 3f -> 2f
        normalized < 7f -> 5f
        else -> 10f
    }
    return niceMult * mag
}
