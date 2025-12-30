package calendar_app.v1.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PendingChangeDao {

    @Query("SELECT * FROM pending_changes ORDER BY createdAtMillis ASC")
    suspend fun getPendingChanges(): List<PendingChangeEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(change: PendingChangeEntity): Long

    @Query("DELETE FROM pending_changes WHERE id IN (:ids)")
    suspend fun deleteByIds(ids: List<Long>)

    @Query("UPDATE pending_changes SET eventId = :newEventId WHERE eventId = :oldEventId")
    suspend fun retargetEvent(oldEventId: Int, newEventId: Int)

    @Query("DELETE FROM pending_changes WHERE eventId = :eventId AND changeType = :type")
    suspend fun deleteByEventAndType(eventId: Int, type: PendingChangeType)
}
