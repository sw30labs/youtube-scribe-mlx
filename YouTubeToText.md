# YouTubeToText

Transcribe YouTube links using your existing local YouTube transcription setup.

## From Share → Copy link

1. In YouTube, choose **Share → Copy link**.
2. Open **YouTubeToText** in Applications (or find it with Spotlight).
3. Choose the speech-to-text model. That choice is saved as the default until you change it.
4. Choose **Add copied link**.

The app saves the link in **Desktop → YouTubeToText**, then processes new links in that folder. Progress appears in Terminal. When one transcript finishes, its text file opens in TextEdit, ready to select and copy. If several finish, the output folder opens.

## From a drop folder

Save YouTube link files in **Desktop → YouTubeToText**, then open the app, pick the STT model, and choose **Process folder**.

Accepted files:

- **.webloc** — a browser link dragged to Finder.
- **.txt** — a plain-text file containing one or several YouTube links (one per line works well).
- **.url** — an Internet shortcut file containing a YouTube link.

The app checks files directly inside the folder. It runs when you open it; it does not watch continuously. It leaves your link files in place, so you can keep or remove them after processing.

## What it does automatically

- Uses the existing `youtube` conda environment without opening VS Code or activating it manually.
- Asks for an STT model first (Parakeet is the recommended default; Whisper large-v3-turbo is still there). The choice is stored in `Desktop/YouTubeToText/.stt.json` and `~/.config/mlx-youtube-scribe/stt.json`.
- Runs the same transcription pipeline as option **2** in `main_langgraph.py` with the selected STT.
- Selects the video identified in the link, discarding playlist, tracking and timestamp parameters. A playlist-only link needs to be replaced with a video Share link.
- Keeps the video-saving option off.
- Remembers completed YouTube video IDs, including when the same video is dropped using a different share link.
- Retries failed videos next time. Successful videos are recorded only after a complete text file exists.

## Where to find things

- App: `/Applications/YouTubeToText.app`
- Drop folder: `/Users/spider/Desktop/YouTubeToText`
- Ready-to-copy text files: `/Users/spider/Desktop/YouTubeToText/output`
- Run logs: `/Users/spider/Desktop/YouTubeToText/logs` (see `last-run.log`)

Each text filename includes the video title and video ID, so videos with the same title cannot overwrite one another. Text uses the existing pipeline's format: video information followed by the transcript.

The hidden `.work` folder keeps the downloaded WAV audio and the pipeline's JSON/text originals. The hidden `.processed.json` file remembers completed videos. Keep those files for recovery and to avoid repeat work. If an exported text file is removed, the next run restores it from the saved original when possible.

The app reuses your existing downloader's Chrome-cookie settings and the selected local STT model. The first run of a new model downloads its weights. Internet access is required for new YouTube downloads. oMLX does not need to be running for this transcription-only workflow. Language behavior matches the existing script (English).

## If something fails

Read the message in Terminal or the latest log. The app continues with other valid links. Fix or remove an invalid link file and open the app again; failed videos are retried. If another run is already active, wait for it to finish, then open the app again for any links added in the meantime.

## Source files

The project contains `src/youtube_inbox.py`, `run_youtube_inbox.sh`, `tests/test_youtube_inbox.py`, and a copy of the app bundle under `macos/YouTubeToText.app`. Existing AudioToMoM and the interactive YouTube workflow are unchanged.

For a queue preview without downloading or transcribing:

```sh
/Users/spider/REPOS/mlx-youtube-scribe-omlx/run_youtube_inbox.sh --dry-run
```
