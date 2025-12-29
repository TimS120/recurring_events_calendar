package calendar_app.v1.model

import java.time.LocalDate
import java.time.format.DateTimeFormatter

enum class FrequencyUnit(val apiValue: String) {
    DAYS("days"),
    WEEKS("weeks"),
    MONTHS("months"),
    YEARS("years");

    companion object {
        fun fromApi(value: String): FrequencyUnit =
            entries.firstOrNull { it.apiValue.equals(value, ignoreCase = true) } ?: DAYS
    }
}

data class EventHistory(
    val id: Int,
    val actionDate: LocalDate,
    val action: String,
    val note: String? = null
)

data class RecurringEvent(
    val id: Int,
    val name: String,
    val frequencyValue: Int,
    val frequencyUnit: FrequencyUnit,
    val dueDate: LocalDate,
    val lastDone: LocalDate?,
    val isOverdue: Boolean,
    val history: List<EventHistory>
) {
    val cadenceText: String
        get() {
            val unitLabel = when (frequencyUnit) {
                FrequencyUnit.DAYS -> if (frequencyValue == 1) "day" else "days"
                FrequencyUnit.WEEKS -> if (frequencyValue == 1) "week" else "weeks"
                FrequencyUnit.MONTHS -> if (frequencyValue == 1) "month" else "months"
                FrequencyUnit.YEARS -> if (frequencyValue == 1) "year" else "years"
            }
            return "Every $frequencyValue $unitLabel"
        }
}

data class TimelineHorizon(
    val label: String,
    val spanDays: Int,
    val sliderRange: IntRange,
    val tickFormatter: DateTimeFormatter
)

val TimelineHorizons: List<TimelineHorizon> = listOf(
    TimelineHorizon(
        label = "Day",
        spanDays = 30,
        sliderRange = -60..120,
        tickFormatter = DateTimeFormatter.ofPattern("MMM d")
    ),
    TimelineHorizon(
        label = "Month",
        spanDays = 180,
        sliderRange = -365..365,
        tickFormatter = DateTimeFormatter.ofPattern("MMM uuuu")
    ),
    TimelineHorizon(
        label = "Year",
        spanDays = 720,
        sliderRange = -365..1825,
        tickFormatter = DateTimeFormatter.ofPattern("uuuu")
    )
)

const val DEFAULT_HISTORY_LIMIT = 12
