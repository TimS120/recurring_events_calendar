package calendar_app.v1.data.local

import androidx.room.TypeConverter
import calendar_app.v1.data.local.PendingChangeType.CREATE
import java.time.LocalDate

class Converters {

    @TypeConverter
    fun fromEpochDay(value: Long?): LocalDate? = value?.let(LocalDate::ofEpochDay)

    @TypeConverter
    fun toEpochDay(value: LocalDate?): Long? = value?.toEpochDay()

    @TypeConverter
    fun fromPendingChange(value: String?): PendingChangeType? =
        value?.let { PendingChangeType.valueOf(it) }

    @TypeConverter
    fun toPendingChange(value: PendingChangeType?): String? = value?.name
}
