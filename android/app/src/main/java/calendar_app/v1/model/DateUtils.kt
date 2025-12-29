package calendar_app.v1.model

import java.time.LocalDate

fun addFrequency(base: LocalDate, value: Int, unit: FrequencyUnit): LocalDate =
    when (unit) {
        FrequencyUnit.DAYS -> base.plusDays(value.toLong())
        FrequencyUnit.WEEKS -> base.plusWeeks(value.toLong())
        FrequencyUnit.MONTHS -> base.plusMonths(value.toLong())
        FrequencyUnit.YEARS -> base.plusYears(value.toLong())
    }
