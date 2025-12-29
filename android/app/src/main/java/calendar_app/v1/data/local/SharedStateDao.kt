package calendar_app.v1.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface SharedStateDao {

    @Query("SELECT * FROM shared_state WHERE id = 1")
    fun watchState(): Flow<SharedStateEntity?>

    @Query("SELECT * FROM shared_state WHERE id = 1")
    suspend fun getState(): SharedStateEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: SharedStateEntity)
}
