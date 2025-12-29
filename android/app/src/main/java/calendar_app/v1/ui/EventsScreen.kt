@file:OptIn(ExperimentalMaterial3Api::class)

package calendar_app.v1.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import calendar_app.v1.model.FrequencyUnit
import calendar_app.v1.model.RecurringEvent
import calendar_app.v1.model.TimelineHorizons
import calendar_app.v1.model.addFrequency
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlin.math.max
import kotlin.math.roundToInt

private val RowHeight = 84.dp
private val AxisPadding = 36.dp

@Composable
fun EventsScreen(
    state: EventsScreenState,
    onTimelineOffsetChange: (Int) -> Unit,
    onHorizonSelected: (Int) -> Unit,
    onSync: () -> Unit,
    onOpenEditor: (RecurringEvent?) -> Unit,
    onMarkDone: (Int) -> Unit,
    onDeleteEvent: (Int) -> Unit,
    onToggleSettings: (Boolean) -> Unit,
    onTokenChange: (String) -> Unit,
    onManualHostChange: (String) -> Unit,
    onManualPortChange: (String) -> Unit,
    onApplySettings: () -> Unit,
    onEditorNameChange: (String) -> Unit,
    onEditorDueDateChange: (String) -> Unit,
    onEditorFrequencyValueChange: (String) -> Unit,
    onEditorUnitChange: (FrequencyUnit) -> Unit,
    onSubmitEditor: () -> Unit,
    onCloseEditor: () -> Unit,
    onClearMessage: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState()
    if (state.showSettings) {
        ModalBottomSheet(
            sheetState = sheetState,
            onDismissRequest = { onToggleSettings(false) }
        ) {
            SettingsSheet(
                state = state,
                onTokenChange = onTokenChange,
                onHostChange = onManualHostChange,
                onPortChange = onManualPortChange,
                onApply = {
                    onApplySettings()
                    onToggleSettings(false)
                }
            )
        }
    }

    state.editorState?.let { editor ->
        EventEditorDialog(
            editor = editor,
            onNameChange = onEditorNameChange,
            onDueDateChange = onEditorDueDateChange,
            onFrequencyChange = onEditorFrequencyValueChange,
            onUnitChange = onEditorUnitChange,
            onConfirm = onSubmitEditor,
            onDismiss = onCloseEditor,
            onDelete = editor.id?.let { id -> { onDeleteEvent(id) } }
        )
    }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        val availableWidth = this.maxWidth
        val scrollState = rememberScrollState()
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
                .padding(12.dp)
        ) {
            TopBar(
                state = state,
                onHorizonSelected = onHorizonSelected,
                onNewEvent = { onOpenEditor(null) },
                onSync = onSync,
                onShowSettings = { onToggleSettings(true) }
            )
            Spacer(Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Drag the timeline to pan through time", style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = { onTimelineOffsetChange(0) }) {
                    Text("Today")
                }
            }
            Spacer(Modifier.height(12.dp))
            EventsTable(
                state = state,
                onOpenEditor = onOpenEditor,
                onMarkDone = onMarkDone,
                onDeleteEvent = onDeleteEvent,
                maxWidth = availableWidth,
                onTimelineOffsetChange = onTimelineOffsetChange
            )
            Spacer(Modifier.height(12.dp))
            AnimatedVisibility(visible = state.statusMessage != null || state.errorMessage != null) {
                val statusColor = if (state.errorMessage != null) Color(0xFFC53030) else Color(0xFF2F855A)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(statusColor.copy(alpha = 0.1f))
                        .padding(12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = state.errorMessage ?: state.statusMessage.orEmpty(),
                        color = statusColor,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = onClearMessage) {
                        Text("Dismiss")
                    }
                }
            }
        }
    }
}

@Composable
private fun TopBar(
    state: EventsScreenState,
    onHorizonSelected: (Int) -> Unit,
    onNewEvent: () -> Unit,
    onSync: () -> Unit,
    onShowSettings: () -> Unit
) {
    val expanded = remember { mutableStateOf(false) }
    TopAppBar(
        title = { Text("Recurring Events") },
        actions = {
            Button(onClick = onSync, enabled = !state.isSyncing) {
                Text(if (state.isSyncing) "Syncing…" else "Sync now")
            }
            IconButton(onClick = onShowSettings) {
                Icon(imageVector = Icons.Filled.Settings, contentDescription = "Settings")
            }
        },
        navigationIcon = {
            Button(onClick = onNewEvent) {
                Text("New")
            }
        }
    )
    Spacer(Modifier.height(8.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Horizon:", fontWeight = FontWeight.Medium)
        Spacer(Modifier.width(8.dp))
        Box {
            Button(onClick = { expanded.value = true }) {
                Text(state.horizon.label)
            }
            DropdownMenu(expanded = expanded.value, onDismissRequest = { expanded.value = false }) {
                TimelineHorizons.forEachIndexed { index, horizon ->
                    DropdownMenuItem(
                        text = { Text(horizon.label) },
                        onClick = {
                            onHorizonSelected(index)
                            expanded.value = false
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun EventsTable(
    state: EventsScreenState,
    onOpenEditor: (RecurringEvent) -> Unit,
    onMarkDone: (Int) -> Unit,
    onDeleteEvent: (Int) -> Unit,
    maxWidth: Dp,
    onTimelineOffsetChange: (Int) -> Unit
) {
    val viewStart = LocalDate.now().plusDays(state.timelineOffsetDays.toLong())
    val viewEnd = viewStart.plusDays(state.horizon.spanDays.toLong())
    val visibleEvents = state.visibleEvents
    val rowsCount = visibleEvents.size.coerceAtLeast(1)
    val timelineHeight = maxOf(RowHeight * rowsCount + AxisPadding, 220.dp)
    val listWidth = 240.dp
    val timelineWidth = maxOf(maxWidth - listWidth - 24.dp, 300.dp)
    val horizontalScroll = rememberScrollState()
    val sliderRange = state.horizon.sliderRange

    @Composable
    fun EventList(modifier: Modifier) {
        Column(modifier = modifier) {
            visibleEvents.forEach { event ->
                EventCard(
                    event = event,
                    onClick = { onOpenEditor(event) },
                    onMarkDone = { onMarkDone(event.id) }
                )
                Spacer(Modifier.height(8.dp))
            }
            if (visibleEvents.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp)
                ) {
                    Text("No events yet. Sync to fetch from PC.", color = Color.Gray)
                }
            }
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(horizontalScroll)
            .height(timelineHeight)
    ) {
        EventList(modifier = Modifier.widthIn(min = listWidth, max = listWidth))
        Spacer(Modifier.width(12.dp))
        var timelineWidthPx by remember { mutableStateOf(1f) }
        Box(
            modifier = Modifier
                .width(timelineWidth)
                .fillMaxHeight()
                .onSizeChanged { timelineWidthPx = it.width.toFloat().coerceAtLeast(1f) }
                .pointerInput(state.horizon, state.timelineOffsetDays, timelineWidthPx) {
                    detectHorizontalDragGestures { change, dragAmount ->
                        change.consume()
                        val daysDelta = (dragAmount / timelineWidthPx) * state.horizon.spanDays
                        val newValue = (state.timelineOffsetDays - daysDelta.roundToInt()).coerceIn(
                            sliderRange.first,
                            sliderRange.last
                        )
                        onTimelineOffsetChange(newValue)
                    }
                }
        ) {
            TimelineCanvas(
                events = visibleEvents,
                viewStart = viewStart,
                viewEnd = viewEnd,
                labelFormatter = state.horizon.tickFormatter
            )
        }
    }
}

@Composable
private fun EventCard(
    event: RecurringEvent,
    onClick: () -> Unit,
    onMarkDone: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = if (event.isOverdue) Color(0xFFFFF1F0) else Color(0xFFF6F7FB))
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(event.name, fontWeight = FontWeight.Bold, fontSize = 18.sp)
            Text(event.cadenceText, color = Color(0xFF4A5568))
            val dueStatus = when {
                event.dueDate == LocalDate.now() -> "Due today"
                event.dueDate.isBefore(LocalDate.now()) -> "Overdue since ${event.dueDate}"
                else -> "Next due ${event.dueDate}"
            }
            Text(dueStatus, color = if (event.isOverdue) Color(0xFFC53030) else Color(0xFF2F855A))
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = onMarkDone) { Text("Done today") }
        }
    }
}

@Composable
private fun TimelineCanvas(
    events: List<RecurringEvent>,
    viewStart: LocalDate,
    viewEnd: LocalDate,
    labelFormatter: DateTimeFormatter
) {
    if (events.isEmpty()) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFFF7F7F7)),
            contentAlignment = Alignment.Center
        ) {
            Text("No events to display")
        }
        return
    }
    val density = LocalDensity.current
    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
    ) {
        val leftPadding = 32.dp.toPx()
        val topPadding = AxisPadding.toPx()
        val rowHeightPx = RowHeight.toPx()
        val width = size.width - leftPadding * 2
        val totalDays = max(1f, ChronoUnit.DAYS.between(viewStart, viewEnd).toFloat())

        fun dateToX(date: LocalDate): Float {
            val delta = ChronoUnit.DAYS.between(viewStart, date).toFloat()
            val ratio = (delta / totalDays).coerceIn(0f, 1f)
            return leftPadding + ratio * width
        }

        // Axis
        drawLine(
            color = Color.Black,
            start = Offset(leftPadding, topPadding - 20),
            end = Offset(size.width - leftPadding, topPadding - 20),
            strokeWidth = 4f
        )

        val tickStep = max(1L, (totalDays / 8f).roundToInt().toLong())
        val labelPaint = android.graphics.Paint().apply {
            color = android.graphics.Color.DKGRAY
            textSize = 28f
            textAlign = android.graphics.Paint.Align.CENTER
        }
        var tickDate = viewStart
        while (!tickDate.isAfter(viewEnd)) {
            val x = dateToX(tickDate)
            drawLine(
                color = Color.DarkGray,
                start = Offset(x, topPadding - 24),
                end = Offset(x, topPadding - 16),
                strokeWidth = 2f
            )
            drawContext.canvas.nativeCanvas.drawText(
                labelFormatter.format(tickDate),
                x,
                topPadding - 30,
                labelPaint
            )
            tickDate = tickDate.plusDays(tickStep)
        }

        val todayX = dateToX(LocalDate.now())
        drawLine(
            color = Color(0xFFFF8800),
            start = Offset(todayX, topPadding - 20),
            end = Offset(todayX, size.height),
            strokeWidth = 3f
        )

        events.forEachIndexed { index, event ->
            val rowTop = topPadding + index * rowHeightPx
            val rowBottom = rowTop + rowHeightPx - 12f
            val midY = (rowTop + rowBottom) / 2f
            drawRect(
                color = if (event.isOverdue) Color(0xFFFFE4E1) else Color(0xFFE8F0FF),
                topLeft = Offset(leftPadding, rowTop),
                size = androidx.compose.ui.geometry.Size(width, rowBottom - rowTop)
            )
            drawLine(
                color = Color(0xFF4A5568),
                start = Offset(leftPadding, midY),
                end = Offset(leftPadding + width, midY),
                strokeWidth = 2f
            )

            event.history.forEach { history ->
                if (history.actionDate in viewStart..viewEnd) {
                    val hx = dateToX(history.actionDate)
                    drawCircle(
                        color = Color(0xFF2F855A),
                        radius = 8f,
                        center = Offset(hx, midY)
                    )
                }
            }

            var markerDate = event.dueDate
            var iterations = 0
            while (!markerDate.isAfter(viewEnd) && iterations < 12) {
                if (!markerDate.isBefore(viewStart)) {
                    val mx = dateToX(markerDate)
                    val overdue = markerDate.isBefore(LocalDate.now()) || markerDate == LocalDate.now()
                    val color = if (overdue) Color(0xFFC53030) else Color(0xFF1A73E8)
                    drawLine(
                        color = color,
                        start = Offset(mx, midY - 20),
                        end = Offset(mx, midY + 20),
                        strokeWidth = 4f
                    )
                }
                markerDate = addFrequency(markerDate, event.frequencyValue, event.frequencyUnit)
                iterations++
            }
        }
    }
}

@Composable
private fun SettingsSheet(
    state: EventsScreenState,
    onTokenChange: (String) -> Unit,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onApply: () -> Unit
) {
    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Connection Settings", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = state.settings.token,
            onValueChange = onTokenChange,
            label = { Text("Bearer token") },
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedTextField(
            value = state.settings.manualHost,
            onValueChange = onHostChange,
            label = { Text("Manual host (optional)") },
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedTextField(
            value = state.settings.manualPort,
            onValueChange = onPortChange,
            label = { Text("Port") },
            modifier = Modifier.fillMaxWidth()
        )
        Text(
            "Leave host empty to auto-discover `_recurringevents._tcp` on your network.",
            style = MaterialTheme.typography.bodySmall
        )
        Button(onClick = onApply, modifier = Modifier.align(Alignment.End)) {
            Text("Apply")
        }
    }
}

@Composable
private fun EventEditorDialog(
    editor: EventEditorState,
    onNameChange: (String) -> Unit,
    onDueDateChange: (String) -> Unit,
    onFrequencyChange: (String) -> Unit,
    onUnitChange: (FrequencyUnit) -> Unit,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    onDelete: (() -> Unit)?
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(onClick = onConfirm) { Text("Save") }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                onDelete?.let {
                    TextButton(onClick = it) { Text("Delete") }
                }
                TextButton(onClick = onDismiss) { Text("Cancel") }
            }
        },
        title = { Text(if (editor.id == null) "New Event" else "Edit Event") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = editor.name,
                    onValueChange = onNameChange,
                    label = { Text("Name") },
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = editor.dueDate,
                    onValueChange = onDueDateChange,
                    label = { Text("Due date (YYYY-MM-DD)") },
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = editor.frequencyValue,
                    onValueChange = onFrequencyChange,
                    label = { Text("Frequency value") },
                    modifier = Modifier.fillMaxWidth()
                )
                FrequencyDropdown(
                    selected = editor.frequencyUnit,
                    onSelected = onUnitChange
                )
            }
        }
    )
}

@Composable
private fun FrequencyDropdown(
    selected: FrequencyUnit,
    onSelected: (FrequencyUnit) -> Unit
) {
    val expanded = remember { mutableStateOf(false) }
    Column {
        Text("Frequency unit", fontWeight = FontWeight.Medium)
        Button(onClick = { expanded.value = true }) {
            Text(selected.apiValue)
        }
        DropdownMenu(
            expanded = expanded.value,
            onDismissRequest = { expanded.value = false }
        ) {
            FrequencyUnit.entries.forEach { unit ->
                DropdownMenuItem(
                    text = { Text(unit.apiValue) },
                    onClick = {
                        onSelected(unit)
                        expanded.value = false
                    }
                )
            }
        }
    }
}
