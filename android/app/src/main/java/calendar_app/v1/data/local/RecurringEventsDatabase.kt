package calendar_app.v1.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(
    entities = [EventEntity::class, EventHistoryEntity::class, PendingChangeEntity::class],
    version = 2,
    exportSchema = false
)
@TypeConverters(Converters::class)
abstract class RecurringEventsDatabase : RoomDatabase() {

    abstract fun eventDao(): EventDao
    abstract fun pendingChangeDao(): PendingChangeDao

    companion object {
        @Volatile
        private var instance: RecurringEventsDatabase? = null

        fun getInstance(context: Context): RecurringEventsDatabase =
            instance ?: synchronized(this) {
                instance ?: buildDatabase(context).also { instance = it }
            }

        private fun buildDatabase(context: Context): RecurringEventsDatabase =
            Room.databaseBuilder(
                context.applicationContext,
                RecurringEventsDatabase::class.java,
                "recurring_events.db"
            ).fallbackToDestructiveMigration()
                .build()
    }
}
