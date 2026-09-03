package calendar_app.v1.data.firebase

import calendar_app.v1.model.EventHistory
import calendar_app.v1.model.FrequencyUnit
import calendar_app.v1.model.RecurringEvent
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.tasks.await
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

class FirestoreCalendarStore(
    private val auth: FirebaseAuthManager,
    private val firestore: FirebaseFirestore = FirebaseFirestore.getInstance()
) {
    private fun document() = firestore.collection("users").document(auth.userId ?: error("Sign in first"))
        .collection("calendars").document("main")

    data class Snapshot(val exists: Boolean, val events: List<RecurringEvent>, val deletedIds: Set<Int>)

    suspend fun read(): Snapshot {
        val snapshot = document().get().await()
        val events = snapshot.get("events") as? List<Map<String, Any?>> ?: emptyList()
        val deletedIds = (snapshot.get("deletedIds") as? List<*>)
            .orEmpty().mapNotNull { (it as? Number)?.toInt() }.toSet()
        return Snapshot(snapshot.exists(), events.map(::decode), deletedIds)
    }

    suspend fun write(events: List<RecurringEvent>, deletedIds: Set<Int> = emptySet()) {
        document().set(mapOf("schemaVersion" to 1, "events" to events.map(::encode), "deletedIds" to deletedIds.sorted())).await()
    }

    /** Clears this account's shared calendar document. The caller clears its local cache as well. */
    suspend fun clearCalendar() {
        document().set(mapOf("schemaVersion" to 1, "events" to emptyList<Map<String, Any?>>(), "deletedIds" to emptyList<Int>())).await()
    }

    private fun encode(event: RecurringEvent) = mapOf(
        "id" to event.id, "name" to event.name, "tag" to event.tag, "details" to event.details,
        "frequencyValue" to event.frequencyValue, "frequencyUnit" to event.frequencyUnit.apiValue,
        "dueDate" to event.dueDate.toString(), "lastDone" to event.lastDone?.toString(),
        // The desktop client stores timestamps as this exact ISO-8601 form.
        "updatedAt" to CANONICAL_TIMESTAMP.format(Instant.now()),
        "history" to event.history.map { mapOf("id" to it.id, "action" to it.action, "actionDate" to it.actionDate.toString(), "note" to it.note) }
    )

    private fun decode(raw: Map<String, Any?>): RecurringEvent {
        val history = (raw["history"] as? List<Map<String, Any?>>).orEmpty().map {
            EventHistory((it["id"] as Number).toInt(), LocalDate.parse(it["actionDate"] as String), it["action"] as String, it["note"] as? String)
        }
        val due = LocalDate.parse(raw["dueDate"] as String)
        return RecurringEvent((raw["id"] as Number).toInt(), raw["name"] as String, raw["tag"] as? String, raw["details"] as? String,
            (raw["frequencyValue"] as Number).toInt(), FrequencyUnit.fromApi(raw["frequencyUnit"] as String), due,
            (raw["lastDone"] as? String)?.let(LocalDate::parse), !due.isAfter(LocalDate.now()), history)
    }

    private companion object {
        val CANONICAL_TIMESTAMP: DateTimeFormatter =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss").withZone(ZoneOffset.UTC)
    }
}
