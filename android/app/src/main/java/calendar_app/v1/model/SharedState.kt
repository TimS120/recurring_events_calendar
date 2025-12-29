package calendar_app.v1.model

data class SharedState(
    val value: Int,
    val updatedAt: Long,
    val sourceId: String
)

fun shouldReplace(incoming: SharedState, current: SharedState): Boolean {
    return when {
        incoming.updatedAt > current.updatedAt -> true
        incoming.updatedAt < current.updatedAt -> false
        else -> incoming.sourceId > current.sourceId
    }
}
