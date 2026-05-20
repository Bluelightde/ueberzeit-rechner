package de.bluelight.ueberzeitrechner.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "entries")
data class WorkEntryEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val date: String,
    val start: String?,
    val end: String?,
    val pause: Int,
    val minutes: Int,
    val reason: String?,
    @ColumnInfo(name = "target_minutes", defaultValue = "-1") val targetMinutes: Int = -1
)
