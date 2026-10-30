class_name SfxBank
extends Node

const SAMPLE_RATE := 22050

var _player: AudioStreamPlayer
var _streams: Dictionary = {}
var enabled := true


func _ready() -> void:
	_player = AudioStreamPlayer.new()
	_player.volume_db = -10.0
	add_child(_player)
	_streams.click = _make_tone([520.0], 0.055, 0.22)
	_streams.start = _make_tone([360.0, 520.0], 0.075, 0.25)
	_streams.coin = _make_tone([660.0, 880.0, 1100.0], 0.085, 0.24)
	_streams.upgrade = _make_tone([440.0, 660.0, 920.0], 0.095, 0.24)
	_streams.level = _make_tone([523.25, 659.25, 783.99, 1046.5], 0.12, 0.26)
	_streams.event = _make_tone([392.0, 587.33, 783.99], 0.11, 0.25)
	_streams.contract = _make_tone([349.23, 523.25, 698.46, 1046.5], 0.1, 0.25)
	_streams.review = _make_tone([659.25, 783.99, 987.77], 0.09, 0.22)


func play_cue(cue: String) -> void:
	if not enabled or not _streams.has(cue):
		return
	_player.stream = _streams[cue]
	_player.play()


func set_enabled(value: bool) -> void:
	enabled = value
	if not enabled and _player:
		_player.stop()


func _make_tone(frequencies: Array[float], note_duration: float, volume: float) -> AudioStreamWAV:
	var sample_count := int(float(SAMPLE_RATE) * note_duration * frequencies.size())
	var data := PackedByteArray()
	data.resize(sample_count * 2)
	var write_index := 0
	for frequency in frequencies:
		var note_samples := int(float(SAMPLE_RATE) * note_duration)
		for sample_index in range(note_samples):
			var phase := float(sample_index) / float(SAMPLE_RATE)
			var envelope := sin(PI * float(sample_index) / float(note_samples))
			var sample := int(sin(TAU * frequency * phase) * envelope * volume * 32767.0)
			data[write_index] = sample & 0xff
			data[write_index + 1] = (sample >> 8) & 0xff
			write_index += 2
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false
	stream.data = data
	return stream
