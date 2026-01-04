package calendar_app.v1.ui

import java.time.LocalDate
import java.time.format.DateTimeFormatter

val DisplayDateFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")

fun formatDisplayDate(date: LocalDate): String = date.format(DisplayDateFormatter)

fun parseDisplayDateOrNull(raw: String): LocalDate? = runCatching {
    LocalDate.parse(raw.trim(), DisplayDateFormatter)
}.getOrNull()
