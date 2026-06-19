package de.bluelight.ueberzeitrechner.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [WorkEntryEntity::class, BereitschaftEntryEntity::class],
    version = 2,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun entriesDao(): EntriesDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                // No fallbackToDestructiveMigration(): a future schema change must ship
                // an explicit Migration via addMigrations(...) instead of silently
                // wiping the user's data. The current schema is version 2; there is no
                // earlier published version to migrate from.
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "ueberstunden_daten.db"
                )
                    .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
