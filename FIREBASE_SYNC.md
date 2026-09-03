# Firebase synchronization

The shared source of truth is `users/{uid}/calendars/main` in Cloud Firestore.
It contains the current event list, completion history and a schema version.
Each device keeps its existing local database as an offline cache and uses a
persistent Firebase Auth session. The PC refresh token is held in Windows
Credential Manager; Android uses Firebase Auth's persisted session.

The Firestore rules in `firestore.rules` permit access only to the signed-in
user's own calendar document.
