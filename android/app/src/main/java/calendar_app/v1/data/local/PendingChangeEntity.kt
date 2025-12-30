package calendar_app.v1.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pending_changes")
data class PendingChangeEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val eventId: Int,
    val changeType: PendingChangeType,
    val payload: String?,
    val createdAtMillis: Long = System.currentTimeMillis()
)

enum class PendingChangeType {
    CREATE,
    UPDATE,
    DELETE,
    MARK_DONE
}
