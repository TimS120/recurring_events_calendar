@file:OptIn(ExperimentalMaterial3Api::class)

package calendar_app.v1.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.AnimationState
import androidx.compose.animation.core.animateDecay
import androidx.compose.animation.core.exponentialDecay
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
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
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
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
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
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
import androidx.compose.ui.window.PopupProperties
import calendar_app.v1.model.FrequencyUnit
import calendar_app.v1.model.RecurringEvent
import calendar_app.v1.model.TimelineHorizons
import calendar_app.v1.model.addFrequency
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.roundToInt
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

private val DefaultRowHeight = 176.dp
private val RowSpacing = 8.dp
private val AxisPadding = 36.dp

@Composable
fun EventsScreen(
    state: EventsScreenState,
    isDarkTheme: Boolean,
    isUsingSystemTheme: Boolean,
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
    onEditorTagChange: (String) -> Unit,
    onEditorDueDateChange: (String) -> Unit,
    onEditorFrequencyValueChange: (String) -> Unit,
    onEditorUnitChange: (FrequencyUnit) -> Unit,
    onSubmitEditor: () -> Unit,
    onCloseEditor: () -> Unit,
    onClearMessage: () -> Unit,
    onToggleDarkMode: () -> Unit,
    onTagPrioritySelected: (String?) -> Unit
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
            onTagChange = onEditorTagChange,
            onDueDateChange = onEditorDueDateChange,
            onFrequencyChange = onEditorFrequencyValueChange,
            onUnitChange = onEditorUnitChange,
            onConfirm = onSubmitEditor,
            onDismiss = onCloseEditor,
            tagSuggestions = state.availableTags,
            onDelete = editor.id?.let { id ->
                {
                    onDeleteEvent(id)
                    onCloseEditor()
                }
            },
            onMarkDone = editor.id?.let { id ->
                {
                    onMarkDone(id)
                    onCloseEditor()
                }
            }
        )
    }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        val availableWidth = this.maxWidth
        val scrollState = rememberScrollState()
        var jumpToTodayNonce by remember { mutableIntStateOf(0) }
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
                .padding(12.dp)
        ) {
            HeaderSection(
                state = state,
                isDarkTheme = isDarkTheme,
                onNewEvent = { onOpenEditor(null) },
                onSync = onSync,
            onToggleDarkMode = onToggleDarkMode,
            onShowSettings = { onToggleSettings(true) },
            onHorizonSelected = onHorizonSelected,
            onJumpToToday = {
                jumpToTodayNonce++
                onTimelineOffsetChange(0)
            },
            onTimelineOffsetChange = onTimelineOffsetChange,
            onTagSelected = onTagPrioritySelected,
            selectedTag = state.prioritizedTag,
            availableTags = state.availableTags
        )
            Spacer(Modifier.height(12.dp))
        EventsTable(
            state = state,
            onOpenEditor = onOpenEditor,
            maxWidth = availableWidth,
            onTimelineOffsetChange = onTimelineOffsetChange,
            jumpToTodayTrigger = jumpToTodayNonce
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
private fun HeaderSection(
    state: EventsScreenState,
    isDarkTheme: Boolean,
    onNewEvent: () -> Unit,
    onSync: () -> Unit,
    onToggleDarkMode: () -> Unit,
    onShowSettings: () -> Unit,
    onHorizonSelected: (Int) -> Unit,
    onJumpToToday: () -> Unit,
    onTimelineOffsetChange: (Int) -> Unit,
    onTagSelected: (String?) -> Unit,
    selectedTag: String?,
    availableTags: List<String>
) {
    val expanded = remember { mutableStateOf(false) }
    Text(
        "Recurring Events",
        style = MaterialTheme.typography.headlineSmall,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.onBackground
    )
    Spacer(Modifier.height(8.dp))
    val iconColor = MaterialTheme.colorScheme.onSurface
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(onClick = onNewEvent) {
                Text("New")
            }
            Button(onClick = onSync, enabled = !state.isSyncing) {
                Text(if (state.isSyncing) "Syncing..." else "Sync now")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            IconButton(
                onClick = onToggleDarkMode,
                colors = IconButtonDefaults.iconButtonColors(contentColor = iconColor)
            ) {
                val icon = if (isDarkTheme) Icons.Filled.LightMode else Icons.Filled.DarkMode
                val description = if (isDarkTheme) "Switch to light mode" else "Switch to dark mode"
                Icon(imageVector = icon, contentDescription = description, tint = iconColor)
            }
            IconButton(
                onClick = onShowSettings,
                colors = IconButtonDefaults.iconButtonColors(contentColor = iconColor)
            ) {
                Icon(imageVector = Icons.Filled.Settings, contentDescription = "Settings", tint = iconColor)
            }
        }
    }
    Spacer(Modifier.height(8.dp))
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
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
        TextButton(onClick = onJumpToToday) {
            Text("Today")
        }
    }
    Spacer(Modifier.height(8.dp))
    TagPrioritySelector(
        selectedTag = selectedTag,
        availableTags = availableTags,
        onTagSelected = onTagSelected
    )
}

@Composable
private fun TagPrioritySelector(
    selectedTag: String?,
    availableTags: List<String>,
    onTagSelected: (String?) -> Unit
) {
    val expanded = remember { mutableStateOf(false) }
    Column {
        Text("Prioritize tag", fontWeight = FontWeight.Medium)
        Button(onClick = { expanded.value = true }) {
            Text(selectedTag ?: "All tags")
        }
        DropdownMenu(expanded = expanded.value, onDismissRequest = { expanded.value = false }) {
            DropdownMenuItem(
                text = { Text("All tags") },
                onClick = {
                    onTagSelected(null)
                    expanded.value = false
                }
            )
            availableTags.forEach { tag ->
                DropdownMenuItem(
                    text = { Text(tag) },
                    onClick = {
                        onTagSelected(tag)
                        expanded.value = false
                    }
                )
            }
        }
    }
}

@Composable
private fun EventsTable(
    state: EventsScreenState,
    onOpenEditor: (RecurringEvent) -> Unit,
    maxWidth: Dp,
    onTimelineOffsetChange: (Int) -> Unit,
    jumpToTodayTrigger: Int
) {
    val viewStart = LocalDate.now().plusDays(state.timelineOffsetDays.toLong())
    val viewEnd = viewStart.plusDays(state.horizon.spanDays.toLong())
    val visibleEvents = state.visibleEvents
    val rowSpacing = RowSpacing
    var rowHeight by remember { mutableStateOf(DefaultRowHeight) }
    val rowsCount = visibleEvents.size
    val totalRowsHeight = if (rowsCount > 0) (rowHeight + rowSpacing) * rowsCount else 0.dp
    val timelineHeight = maxOf(totalRowsHeight + AxisPadding, 220.dp)
    val listWidth = 320.dp
    val timelineWidth = maxOf(maxWidth - listWidth - 24.dp, 300.dp)
    val horizontalScroll = rememberScrollState()
    val sliderRange = state.horizon.sliderRange
    val density = LocalDensity.current
    var timelineWidthPx by remember { mutableStateOf(1f) }
    val coroutineScope = rememberCoroutineScope()
    val decaySpec = remember { exponentialDecay<Float>() }
    var flingJob by remember { mutableStateOf<Job?>(null) }
    var accumulatedDays by remember { mutableStateOf(0f) }

    fun stopFling() {
        flingJob?.cancel()
        flingJob = null
    }

    fun handleDragPixels(deltaPx: Float) {
        if (timelineWidthPx <= 0f) return
        if (deltaPx == 0f) return
        val daysDelta = (deltaPx / timelineWidthPx) * state.horizon.spanDays
        if (daysDelta == 0f) return
        accumulatedDays += daysDelta
        if (abs(accumulatedDays) < 0.1f) return
        val steps = accumulatedDays.roundToInt()
        if (steps == 0) return
        val newValue = (state.timelineOffsetDays - steps).coerceIn(
            sliderRange.first,
            sliderRange.last
        )
        accumulatedDays -= steps
        if (newValue != state.timelineOffsetDays) {
            onTimelineOffsetChange(newValue)
        }
    }

    fun startFling(velocity: Float) {
        if (timelineWidthPx <= 0f) return
        stopFling()
        if (velocity == 0f) return
        flingJob = coroutineScope.launch {
            var lastValue = 0f
            AnimationState(initialValue = 0f, initialVelocity = velocity).animateDecay(decaySpec) {
                val delta = value - lastValue
                handleDragPixels(delta)
                lastValue = value
                if (abs(velocity) < 0.01f) this.cancelAnimation()
            }
        }
    }

    val draggableState = rememberDraggableState { delta ->
        stopFling()
        handleDragPixels(delta)
    }

    LaunchedEffect(jumpToTodayTrigger) {
        stopFling()
        accumulatedDays = 0f
    }

    @Composable
    fun EventList(modifier: Modifier) {
        Column(modifier = modifier) {
            if (visibleEvents.isNotEmpty()) {
                Spacer(Modifier.height(AxisPadding))
            }
            visibleEvents.forEachIndexed { index, event ->
                val measureModifier = if (index == 0) {
                    Modifier.onSizeChanged { size ->
                        val measuredHeight = with(density) { size.height.toDp() }
                        if (measuredHeight > 0.dp && rowHeight != measuredHeight) {
                            rowHeight = measuredHeight
                        }
                    }
                } else {
                    Modifier
                }
                EventCard(
                    event = event,
                    modifier = measureModifier,
                    onClick = { onOpenEditor(event) }
                )
                Spacer(Modifier.height(rowSpacing))
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
        Box(
            modifier = Modifier
                .width(timelineWidth)
                .fillMaxHeight()
                .onSizeChanged { timelineWidthPx = it.width.toFloat().coerceAtLeast(1f) }
                .draggable(
                    state = draggableState,
                    orientation = Orientation.Horizontal,
                    onDragStarted = { stopFling() },
                    onDragStopped = { velocity -> startFling(velocity) }
                )
        ) {
            TimelineCanvas(
                events = visibleEvents,
                viewStart = viewStart,
                viewEnd = viewEnd,
                labelFormatter = state.horizon.tickFormatter,
                rowHeight = rowHeight,
                rowSpacing = rowSpacing
            )
        }
    }
}

@Composable
private fun EventCard(
    event: RecurringEvent,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = if (event.isOverdue) Color(0xFFFFF1F0) else Color(0xFFF6F7FB))
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(event.name, fontWeight = FontWeight.Bold, fontSize = 18.sp)
            val secondaryLine = buildString {
                append(event.cadenceText)
                val tagText = event.tag?.trim()?.takeIf { it.isNotEmpty() }
                if (tagText != null) {
                    append(" | Tag: ")
                    append(tagText)
                }
            }
            Text(secondaryLine, color = Color(0xFF4A5568))
            val dueStatus = when {
                event.dueDate == LocalDate.now() -> "Due today"
                event.dueDate.isBefore(LocalDate.now()) -> "Overdue since ${event.dueDate}"
                else -> "Next due ${event.dueDate}"
            }
            Text(dueStatus, color = if (event.isOverdue) Color(0xFFC53030) else Color(0xFF2F855A))
        }
    }
}

@Composable
private fun TimelineCanvas(
    events: List<RecurringEvent>,
    viewStart: LocalDate,
    viewEnd: LocalDate,
    labelFormatter: DateTimeFormatter,
    rowHeight: Dp,
    rowSpacing: Dp
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
    val rowHeightPx = with(density) { rowHeight.toPx() }
    val rowSpacingPx = with(density) { rowSpacing.toPx() }
    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
    ) {
        val leftPadding = 32.dp.toPx()
        val topPadding = AxisPadding.toPx()
        val width = size.width - leftPadding * 2
        val totalDays = max(1f, ChronoUnit.DAYS.between(viewStart, viewEnd).toFloat())
        val spanDays = max(1, ChronoUnit.DAYS.between(viewStart, viewEnd).toInt())

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

        val today = LocalDate.now()
        val todayX = if (!today.isBefore(viewStart) && !today.isAfter(viewEnd)) {
            dateToX(today)
        } else {
            null
        }

        val rowStride = rowHeightPx + rowSpacingPx
        events.forEachIndexed { index, event ->
            val rowTop = topPadding + index * rowStride
            val rowBottom = rowTop + rowHeightPx
            val midY = (rowTop + rowBottom) / 2f
            drawRect(
                color = if (event.isOverdue) Color(0xFFFFE4E1) else Color(0xFFE8F0FF),
                topLeft = Offset(leftPadding, rowTop),
                size = androidx.compose.ui.geometry.Size(width, rowHeightPx)
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
            val freqDays = estimatedFrequencyDays(event.frequencyValue, event.frequencyUnit)
            val maxIterations = max(24, spanDays / freqDays + 24)
            while (!markerDate.isAfter(viewEnd) && iterations < maxIterations) {
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

        if (todayX != null) {
            drawLine(
                color = Color(0xFFFF8800),
                start = Offset(todayX, topPadding - 20),
                end = Offset(todayX, size.height),
                strokeWidth = 3f
            )
            val todayLabelPaint = android.graphics.Paint(labelPaint).apply {
                textAlign = android.graphics.Paint.Align.LEFT
                color = android.graphics.Color.parseColor("#FF8800")
            }
            drawContext.canvas.nativeCanvas.drawText(
                "Today",
                todayX + 8f,
                topPadding,
                todayLabelPaint
            )
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
    onTagChange: (String) -> Unit,
    onDueDateChange: (String) -> Unit,
    onFrequencyChange: (String) -> Unit,
    onUnitChange: (FrequencyUnit) -> Unit,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
    tagSuggestions: List<String>,
    onDelete: (() -> Unit)?,
    onMarkDone: (() -> Unit)? = null
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(onClick = onConfirm) { Text("Save") }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                onMarkDone?.let {
                    TextButton(onClick = it) { Text("Done today") }
                }
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
                TagSuggestionField(
                    value = editor.tag,
                    onValueChange = onTagChange,
                    suggestions = tagSuggestions
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

@Composable
private fun TagSuggestionField(
    value: String,
    onValueChange: (String) -> Unit,
    suggestions: List<String>
) {
    var expanded by remember { mutableStateOf(false) }
    val trimmedSuggestions = remember(suggestions) {
        suggestions.distinctBy { it.lowercase() }.sortedWith(String.CASE_INSENSITIVE_ORDER)
    }
    val filterSuggestions = remember(trimmedSuggestions) {
        { query: String ->
            val normalized = query.trim()
            if (normalized.isEmpty()) {
                trimmedSuggestions
            } else {
                trimmedSuggestions.filter { it.startsWith(normalized, ignoreCase = true) }
            }
        }
    }
    val filtered = remember(value, trimmedSuggestions) { filterSuggestions(value) }
    Box {
        OutlinedTextField(
            value = value,
            onValueChange = {
                onValueChange(it)
                expanded = filterSuggestions(it).isNotEmpty()
            },
            label = { Text("Tag (optional)") },
            modifier = Modifier
                .fillMaxWidth(),
            trailingIcon = {
                IconButton(
                    onClick = {
                        if (filtered.isNotEmpty()) {
                            expanded = !expanded
                        }
                    },
                    enabled = filtered.isNotEmpty()
                ) {
                    Icon(
                        imageVector = Icons.Filled.ArrowDropDown,
                        contentDescription = "Show tags"
                    )
                }
            },
            singleLine = true
        )
        DropdownMenu(
            expanded = expanded && filtered.isNotEmpty(),
            onDismissRequest = { expanded = false },
            properties = PopupProperties(focusable = false)
        ) {
            filtered.forEach { suggestion ->
                DropdownMenuItem(
                    text = { Text(suggestion) },
                    onClick = {
                        onValueChange(suggestion)
                        expanded = false
                    }
                )
            }
        }
    }
}

private fun estimatedFrequencyDays(value: Int, unit: FrequencyUnit): Int {
    val base = when (unit) {
        FrequencyUnit.DAYS -> 1
        FrequencyUnit.WEEKS -> 7
        FrequencyUnit.MONTHS -> 30
        FrequencyUnit.YEARS -> 365
    }
    return (value * base).coerceAtLeast(1)
}
