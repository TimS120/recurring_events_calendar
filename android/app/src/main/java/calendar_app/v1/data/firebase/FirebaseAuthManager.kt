package calendar_app.v1.data.firebase

import com.google.firebase.auth.FirebaseAuth
import kotlinx.coroutines.tasks.await

/** Firebase Auth persists its refresh session, so a device signs in only once. */
class FirebaseAuthManager(private val auth: FirebaseAuth = FirebaseAuth.getInstance()) {
    val isSignedIn: Boolean get() = auth.currentUser != null
    val userId: String? get() = auth.currentUser?.uid

    suspend fun signIn(email: String, password: String) {
        auth.signInWithEmailAndPassword(email.trim(), password).await()
    }

    suspend fun createAccount(email: String, password: String) {
        auth.createUserWithEmailAndPassword(email.trim(), password).await()
    }

    fun signOut() = auth.signOut()
}
