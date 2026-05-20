package de.bluelight.ueberzeitrechner.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "bereitschaft_entries")
data class BereitschaftEntryEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val date: String,
    val start: String?,
    val end: String?,
    val note: String?,
    @ColumnInfo(name = "end_date") val endDate: String?
)
