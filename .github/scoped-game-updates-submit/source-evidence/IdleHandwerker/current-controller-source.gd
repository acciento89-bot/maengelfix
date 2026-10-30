class_name WorkshopMusic
extends Node

# Original "Werkstatt-Walzer": eight bars in D major, 3/4 at 72 BPM.
# All notes are synthesized here; no recording, vendor/demo track or sampled voice.
const SAMPLE_RATE := 22050
const SECONDS_PER_BEAT := 60.0 / 72.0
const FRAME_COUNT := SAMPLE_RATE * 20
const LEVEL_DB := -16.0
const SILENT_DB := -60.0
const MELODY := [
	[74, 69, 66, 64], [71, 66, 69, 66],
	[67, 71, 74, 71], [69, 73, 76, 73],
	[74, 76, 78, 74], [71, 74, 67, 69],
	[71, 69, 66, 64], [69, 73, 76, 74],
]
const ROOTS := [50, 47, 43, 45, 50, 43, 47, 45]
static var _cached_loop: AudioStreamWAV

var enabled := false
var _player: AudioStreamPlayer
var _fade: Tween
var _started := false
var _application_paused := false
var _window_unfocused := false


static func generate_pcm() -> PackedByteArray:
	var mix := PackedFloat32Array()
	mix.resize(FRAME_COUNT)
	for bar in range(8):
		var beat := float(bar * 3)
		_add_note(mix, beat, 1.6, ROOTS[bar], 0.075, false)
		_add_note(mix, beat + 2.0, 0.7, ROOTS[bar] + 7, 0.04, false)
		for step in range(4):
			_add_note(mix, beat + float(step) * 0.75, 0.65 if step < 3 else 0.45,
				MELODY[bar][step], 0.14 if step == 0 else 0.10, true)
	var pcm := PackedByteArray()
	pcm.resize(FRAME_COUNT * 2)
	for index in range(FRAME_COUNT):
		var sample := int(roundf(clampf(mix[index], -0.75, 0.75) * 32767.0))
		pcm[index * 2] = sample & 0xff
		pcm[index * 2 + 1] = (sample >> 8) & 0xff
	return pcm


static func _add_note(mix: PackedFloat32Array, beat: float, duration: float,
		pitch: int, gain: float, mallet: bool) -> void:
	var start := int(roundf(beat * SECONDS_PER_BEAT * SAMPLE_RATE))
	var count := mini(int(roundf(duration * SECONDS_PER_BEAT * SAMPLE_RATE)), FRAME_COUNT - start)
	var frequency := 440.0 * pow(2.0, float(pitch - 69) / 12.0)
	for index in range(count):
		var t := float(index) / SAMPLE_RATE
		var progress := float(index) / float(count - 1)
		# Smooth attack and zero-value/zero-slope release prevent note/loop clicks.
		var attack := sin(minf(t / 0.014, 1.0) * PI * 0.5)
		var envelope := attack * attack * pow(1.0 - progress, 3.0)
		var phase := TAU * frequency * t
		var partials := sin(phase) + (0.22 if mallet else 0.35) * sin(phase * 2.0)
		partials += (0.06 if mallet else 0.12) * sin(phase * 3.0)
		mix[start + index] += partials * gain * envelope


static func create_loop() -> AudioStreamWAV:
	if _cached_loop == null:
		_cached_loop = AudioStreamWAV.new()
		_cached_loop.format = AudioStreamWAV.FORMAT_16_BITS
		_cached_loop.mix_rate = SAMPLE_RATE
		_cached_loop.stereo = false
		_cached_loop.data = generate_pcm()
		_cached_loop.loop_mode = AudioStreamWAV.LOOP_FORWARD
		_cached_loop.loop_begin = 0
		_cached_loop.loop_end = FRAME_COUNT - 1
	return _cached_loop


func _ready() -> void:
	_player = AudioStreamPlayer.new()
	_player.name = "WorkshopMusicPlayer"
	_player.volume_db = SILENT_DB
	add_child(_player)
	_sync_playback()


func set_enabled(value: bool) -> void:
	if enabled == value:
		return
	enabled = value
	_sync_playback()


func _notification(what: int) -> void:
	match what:
		NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_WM_CLOSE_REQUEST:
			_application_paused = true
		NOTIFICATION_APPLICATION_RESUMED:
			_application_paused = false
		NOTIFICATION_APPLICATION_FOCUS_OUT:
			_window_unfocused = true
		NOTIFICATION_APPLICATION_FOCUS_IN:
			_window_unfocused = false
		_:
			return
	_sync_playback()


func _sync_playback() -> void:
	if not is_instance_valid(_player) or not is_inside_tree():
		return
	if _fade != null and _fade.is_valid():
		_fade.kill()
	if _application_paused or _window_unfocused:
		# An application suspension cannot rely on a future tween frame running.
		_player.volume_db = SILENT_DB
		_player.stream_paused = true
	elif enabled:
		if not _started:
			_player.stream = create_loop()
			_player.play()
			_started = true
		_player.stream_paused = false
		_fade = create_tween()
		_fade.tween_property(_player, "volume_db", LEVEL_DB, 0.10)
	elif _started:
		_fade = create_tween()
		_fade.tween_property(_player, "volume_db", SILENT_DB, 0.07)
		_fade.tween_callback(func() -> void: _player.stream_paused = true)


func _exit_tree() -> void:
	if _fade != null and _fade.is_valid():
		_fade.kill()
	if is_instance_valid(_player):
		_player.stream_paused = false
		_player.stop()
		_player.stream = null
	_started = false
