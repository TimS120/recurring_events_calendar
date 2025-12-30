package calendar_app.v1.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface EventDao {

    @Transaction
    @Query("SELECT * FROM events WHERE deleted = 0 ORDER BY dueDate ASC")
    fun observeEvents(): Flow<List<EventWithHistoryEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertEvents(events: List<EventEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertHistories(history: List<EventHistoryEntity>)

    @Query("DELETE FROM event_history WHERE eventId = :eventId")
    suspend fun deleteHistoryForEvent(eventId: Int)

    @Query("DELETE FROM event_history")
    suspend fun clearHistory()

    @Query("DELETE FROM events")
    suspend fun clearEvents()

    @Query("SELECT * FROM events WHERE id = :eventId LIMIT 1")
    suspend fun getEventById(eventId: Int): EventEntity?

    @Update
    suspend fun updateEvent(entity: EventEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertEvent(entity: EventEntity)

    @Transaction
    suspend fun replaceAll(snapshots: List<Pair<EventEntity, List<EventHistoryEntity>>>) {
        clearHistory()
        clearEvents()
        if (snapshots.isEmpty()) return
        upsertEvents(snapshots.map { it.first })
        upsertHistories(snapshots.flatMap { it.second })
    }

    @Query("UPDATE events SET id = :newId WHERE id = :oldId")
    suspend fun replaceEventId(oldId: Int, newId: Int)

    @Query("UPDATE event_history SET eventId = :newId WHERE eventId = :oldId")
    suspend fun replaceHistoryEventId(oldId: Int, newId: Int)
}
