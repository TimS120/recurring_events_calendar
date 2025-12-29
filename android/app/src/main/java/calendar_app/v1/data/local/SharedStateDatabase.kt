package calendar_app.v1.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [SharedStateEntity::class],
    version = 1,
    exportSchema = false
)
abstract class SharedStateDatabase : RoomDatabase() {

    abstract fun sharedStateDao(): SharedStateDao

    companion object {
        @Volatile
        private var instance: SharedStateDatabase? = null

        fun getInstance(context: Context): SharedStateDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    SharedStateDatabase::class.java,
                    "shared_state.db"
                ).build().also { instance = it }
            }
        }
    }
}
