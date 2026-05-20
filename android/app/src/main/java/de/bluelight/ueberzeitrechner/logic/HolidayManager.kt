package de.bluelight.ueberzeitrechner.logic

import java.time.LocalDate

object HolidayManager {

    /**
     * Gauss algorithm to calculate Easter Sunday for a given year.
     */
    fun getEasterSunday(year: Int): LocalDate {
        val a = year % 19
        val b = year % 4
        val c = year % 7
        val k = year / 100
        val p = (13 + 8 * k) / 25
        val q = k / 4
        val m = (15 - p + k - q) % 30
        val n = (4 + k - q) % 7
        val d = (19 * a + m) % 30
        val e = (2 * b + 4 * c + 6 * d + n) % 7
        val days = 22 + d + e

        return if (d == 29 && e == 6) {
            LocalDate.of(year, 4, 19)
        } else if (d == 28 && e == 6 && (11 * m + 11) % 30 < 19) {
            LocalDate.of(year, 4, 18)
        } else {
            if (days > 31) {
                LocalDate.of(year, 4, days - 31)
            } else {
                LocalDate.of(year, 3, days)
            }
        }
    }

    /**
     * Calculates public holidays for Germany based on the state code (e.g. "BW", "BY").
     * Returns a map of "yyyy-MM-dd" to holiday name.
     */
    fun getGermanHolidays(year: Int, stateCode: String): Map<String, String> {
        val holidays = mutableMapOf<String, String>()

        // Fixed holidays
        holidays["$year-01-01"] = "Neujahr"
        holidays["$year-05-01"] = "Tag der Arbeit"
        holidays["$year-10-03"] = "Tag der Deutschen Einheit"
        holidays["$year-12-25"] = "1. Weihnachtstag"
        holidays["$year-12-26"] = "2. Weihnachtstag"

        // Easter-dependent holidays
        val easter = getEasterSunday(year)
        val goodFriday = easter.minusDays(2)
        val easterMonday = easter.plusDays(1)
        val ascension = easter.plusDays(39)
        val pentecostMonday = easter.plusDays(50)

        holidays[goodFriday.toString()] = "Karfreitag"
        holidays[easterMonday.toString()] = "Ostermontag"
        holidays[ascension.toString()] = "Christi Himmelfahrt"
        holidays[pentecostMonday.toString()] = "Pfingstmontag"

        // State-specific holidays
        when (stateCode.uppercase()) {
            "BW" -> {
                holidays["$year-01-06"] = "Heilige Drei Könige"
                holidays[easter.plusDays(60).toString()] = "Fronleichnam"
                holidays["$year-11-01"] = "Allerheiligen"
            }
            "BY" -> {
                holidays["$year-01-06"] = "Heilige Drei Könige"
                holidays[easter.plusDays(60).toString()] = "Fronleichnam"
                holidays["$year-08-15"] = "Mariä Himmelfahrt"
                holidays["$year-11-01"] = "Allerheiligen"
            }
            "BE" -> {
                holidays["$year-03-08"] = "Internationaler Frauentag"
            }
            "BB" -> {
                holidays[easter.toString()] = "Ostersonntag"
                holidays[easter.plusDays(49).toString()] = "Pfingstsonntag"
                holidays["$year-10-31"] = "Reformationstag"
            }
            "HB", "HH", "NI", "SH" -> {
                holidays["$year-10-31"] = "Reformationstag"
            }
            "HE" -> {
                holidays[easter.plusDays(60).toString()] = "Fronleichnam"
            }
            "MV" -> {
                holidays["$year-03-08"] = "Internationaler Frauentag"
                holidays["$year-10-31"] = "Reformationstag"
            }
            "NW", "RP" -> {
                holidays[easter.plusDays(60).toString()] = "Fronleichnam"
                holidays["$year-11-01"] = "Allerheiligen"
            }
            "SL" -> {
                holidays[easter.plusDays(60).toString()] = "Fronleichnam"
                holidays["$year-08-15"] = "Mariä Himmelfahrt"
                holidays["$year-11-01"] = "Allerheiligen"
            }
            "SN" -> {
                holidays["$year-10-31"] = "Reformationstag"
                // Buß- und Bettag: Wednesday before Nov 23rd
                val nov23 = LocalDate.of(year, 11, 23)
                val dayOfWeek = nov23.dayOfWeek.value // 1 = Monday, 7 = Sunday
                val daysToSubtract = if (dayOfWeek <= 3) dayOfWeek + 4 else dayOfWeek - 3
                holidays[nov23.minusDays(daysToSubtract.toLong()).toString()] = "Buß- und Bettag"
            }
            "ST" -> {
                holidays["$year-01-06"] = "Heilige Drei Könige"
                holidays["$year-10-31"] = "Reformationstag"
            }
            "TH" -> {
                holidays["$year-09-20"] = "Weltkindertag"
                holidays["$year-10-31"] = "Reformationstag"
            }
        }

        return holidays
    }
}
