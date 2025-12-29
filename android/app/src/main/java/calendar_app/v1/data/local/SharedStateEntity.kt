package calendar_app.v1.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey
import calendar_app.v1.model.SharedState

@Entity(tableName = "shared_state")
data class SharedStateEntity(
    @PrimaryKey val id: Int = 1,
    val value: Int,
    val updatedAt: Long,
    val sourceId: String
)

fun SharedStateEntity.toDomain(): SharedState =
    SharedState(value = value, updatedAt = updatedAt, sourceId = sourceId)

fun SharedState.toEntity(): SharedStateEntity =
    SharedStateEntity(value = value, updatedAt = updatedAt, sourceId = sourceId)
