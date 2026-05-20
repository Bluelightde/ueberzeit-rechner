package de.bluelight.ueberzeitrechner.logic

import de.bluelight.ueberzeitrechner.data.WorkEntryEntity
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlin.math.abs

object TimeCalculator {

    private val TIME_FORMATTER = DateTimeFormatter.ofPattern("HH:mm")
    private val DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd")

    /**
     * Renders minutes as a readable string like "8h 30m" or "-1h 15m".
     */
    fun formatMinutes(minutes: Int, showPlus: Boolean = false): String {
        val sign = if (minutes < 0) "-" else if (showPlus && minutes > 0) "+" else ""
        val absMins = abs(minutes)
        val h = absMins / 60
        val m = absMins % 60
        return "$sign${h}h ${m}m"
    }

    /**
     * Parses "HH:mm" to minutes since midnight.
     */
    fun parseTimeToMinutes(timeStr: String?): Int {
        if (timeStr.isNullOrEmpty()) return 0
        return try {
            val t = LocalTime.parse(timeStr, TIME_FORMATTER)
            t.hour * 60 + t.minute
        } catch (e: Exception) {
            0
        }
    }

    /**
     * Calculates the duration in minutes between start and end times, support midnight shifts.
     */
    fun calculateGrossMinutes(start: String?, end: String?): Int {
        if (start.isNullOrEmpty() || end.isNullOrEmpty()) return 0
        return try {
            val s = LocalTime.parse(start, TIME_FORMATTER)
            val e = LocalTime.parse(end, TIME_FORMATTER)
            var diff = ChronoUnit.MINUTES.between(s, e).toInt()
            if (diff < 0) {
                diff += 24 * 60
            }
            diff
        } catch (e: Exception) {
            0
        }
    }

    /**
     * Main calculation engine matching 'calculate_timed_entries' in logic.py
     * Returns a pair:
     * - Map of entry ID to Pair(calculatedPauseMinutes, overtimeMinutes)
     * - Total net minutes for the day
     */
    fun calculateTimedEntries(
        entries: List<WorkEntryEntity>,
        targetMins: Int,
        maxMins: Int,
        isAutoBreak: Boolean
    ): Pair<Map<Int, Pair<Int, Int>>, Int> {
        val sortedEntries = entries.filter { !it.start.isNullOrEmpty() && !it.end.isNullOrEmpty() }
            .sortedBy { it.start ?: "00:00" }

        val results = mutableMapOf<Int, Pair<Int, Int>>()
        var totalAccumulatedGross = 0
        var totalAccumulatedGap = 0
        var recordedPauseDistributed = 0
        var lastEndVal: LocalTime? = null

        for (i in sortedEntries.indices) {
            val e = sortedEntries[i]
            val currentGross = calculateGrossMinutes(e.start, e.end)

            if (lastEndVal != null && !e.start.isNullOrEmpty()) {
                try {
                    val s = LocalTime.parse(e.start, TIME_FORMATTER)
                    var gap = ChronoUnit.MINUTES.between(lastEndVal, s).toInt()
                    if (gap < 0) {
                        gap += 24 * 60
                    }
                    totalAccumulatedGap += maxOf(0, gap)
                } catch (ex: Exception) {
                    // Ignore parsing error
                }
            }

            if (!e.end.isNullOrEmpty()) {
                lastEndVal = LocalTime.parse(e.end, TIME_FORMATTER)
            }

            totalAccumulatedGross += currentGross

            val currentBreak = if (isAutoBreak) {
                var req = 0
                if (totalAccumulatedGross > 540) { // > 9 hours
                    req = 45
                } else if (totalAccumulatedGross > 360) { // > 6 hours
                    req = 30
                }
                val currentTotalPauseNeeded = maxOf(0, req - totalAccumulatedGap)
                maxOf(0, currentTotalPauseNeeded - recordedPauseDistributed)
            } else {
                e.pause
            }

            recordedPauseDistributed += currentBreak

            val overtime = if (i == sortedEntries.lastIndex) {
                val totalNet = totalAccumulatedGross - recordedPauseDistributed
                minOf(maxMins, totalNet) - targetMins
            } else {
                0
            }

            results[e.id] = Pair(currentBreak, overtime)
        }

        val totalNet = minOf(maxMins, totalAccumulatedGross - recordedPauseDistributed)
        return Pair(results, totalNet)
    }
}
