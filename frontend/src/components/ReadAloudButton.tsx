import { useEffect, useRef, useState } from "react";
import { LoaderCircle, Pause, Play, Square, Volume2 } from "lucide-react";

type PlaybackStatus = "idle" | "loading" | "playing" | "paused";

export type ReadAloudButtonProps = {
  restaurantId: number;
  analysisId: number;
  disabled?: boolean;
  fetchAudio: (restaurantId: number, analysisId: number, signal?: AbortSignal) => Promise<Blob>;
};

export function ReadAloudButton({
  restaurantId,
  analysisId,
  disabled = false,
  fetchAudio,
}: ReadAloudButtonProps) {
  const [status, setStatus] = useState<PlaybackStatus>("idle");
  const [error, setError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const cachedKeyRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const cacheKey = `${restaurantId}:${analysisId}`;

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
      if (audioRef.current) {
        audioRef.current.onended = null;
        audioRef.current.onerror = null;
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      cachedKeyRef.current = null;
      setStatus("idle");
      setError("");
    };
  }, [cacheKey]);

  async function handlePrimaryClick() {
    if (status === "loading") return;

    if (status === "playing") {
      audioRef.current?.pause();
      setStatus("paused");
      return;
    }

    if (status === "paused" && audioRef.current) {
      try {
        await audioRef.current.play();
        setStatus("playing");
      } catch {
        setStatus("idle");
        setError("Unable to resume audio playback.");
      }
      return;
    }

    if (audioRef.current && cachedKeyRef.current === cacheKey) {
      setError("");
      audioRef.current.currentTime = 0;
      try {
        await audioRef.current.play();
        setStatus("playing");
      } catch {
        setStatus("idle");
        setError("Unable to play audio.");
      }
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setStatus("loading");
    setError("");

    try {
      const blob = await fetchAudio(restaurantId, analysisId, controller.signal);
      if (controller.signal.aborted) return;

      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
      const objectUrl = URL.createObjectURL(blob);
      const audio = new Audio(objectUrl);
      audio.onended = () => setStatus("idle");
      audio.onerror = () => {
        setStatus("idle");
        setError("Unable to play audio.");
      };

      audioUrlRef.current = objectUrl;
      audioRef.current = audio;
      cachedKeyRef.current = cacheKey;

      await audio.play();
      if (!controller.signal.aborted) {
        setStatus("playing");
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Unable to generate audio.");
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }

  function handleStop() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setStatus("idle");
  }

  const label =
    status === "loading"
      ? "Loading audio..."
      : status === "playing"
        ? "Pause"
        : status === "paused"
          ? "Resume"
          : "Read aloud";

  return (
    <div className="read-aloud-wrapper">
      <div className="read-aloud-controls">
        <button
          type="button"
          className={`read-aloud-button${status === "playing" || status === "paused" ? " active" : ""}`}
          onClick={() => void handlePrimaryClick()}
          disabled={disabled || status === "loading"}
          aria-busy={status === "loading"}
          aria-label={status === "idle" ? "Read analysis summary aloud" : label}
        >
          {status === "loading" ? (
            <LoaderCircle size={13} className="spin" />
          ) : status === "playing" ? (
            <Pause size={13} />
          ) : status === "paused" ? (
            <Play size={13} />
          ) : (
            <Volume2 size={13} />
          )}
          <span>{label}</span>
        </button>
        {(status === "playing" || status === "paused") && (
          <button
            type="button"
            className="read-aloud-stop"
            onClick={handleStop}
            aria-label="Stop reading aloud"
          >
            <Square size={10} fill="currentColor" />
            <span>Stop</span>
          </button>
        )}
      </div>
      <p className="read-aloud-disclosure">This voice is AI-generated.</p>
      {error && (
        <p className="read-aloud-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
