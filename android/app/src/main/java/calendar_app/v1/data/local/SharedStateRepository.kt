package calendar_app.v1.data.local

import calendar_app.v1.model.SharedState
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.map

class SharedStateRepository(
    private val dao: SharedStateDao
) {

    val stateFlow: Flow<SharedState> =
        dao.watchState()
            .filterNotNull()
            .map { it.toDomain() }

    suspend fun ensureSeed(sourceId: String) {
        val existing = dao.getState()
        if (existing == null) {
            val now = System.currentTimeMillis()
            dao.upsert(
                SharedStateEntity(
                    value = 0,
                    updatedAt = now,
                    sourceId = sourceId
                )
            )
        }
    }

    suspend fun getState(): SharedState? = dao.getState()?.toDomain()

    suspend fun save(state: SharedState) {
        dao.upsert(state.toEntity())
    }

    suspend fun applyLocal(value: Int, sourceId: String): SharedState {
        val now = System.currentTimeMillis()
        val updated = SharedState(value = value, updatedAt = now, sourceId = sourceId)
        dao.upsert(updated.toEntity())
        return updated
    }
}
