# Deploying Nyaya Saathi

The plan: **one git repo, pushed to two places.**
- **GitHub**: the code, test cases and `raw_outputs/` that the submission form asks for.
- **Hugging Face Space**: the live app, which is the "prototype link". Creating a Docker Space needs a paid PRO account ($9/month at the time of writing). The CPU Basic hardware itself is free and has 16 GB RAM, which fits the embedding model easily.

The Space builds from the `Dockerfile`:
1. Installs CPU-only torch and the pinned packages.
2. Downloads the embedding model and **builds the search index inside the image**, so no large binary files are uploaded.
3. Starts Streamlit on port 7860.

The first build takes about 5–10 minutes. After that the Space wakes in well under a minute.

---

## 1. Put the project in git (once)

Run these from the `ai-lawyer` folder:

```bash
git init -b main
```

```bash
git add .
```

```bash
git status
```

**Check before committing:** `.env` must not appear in the list. `.gitignore` excludes it, along with `logs/`.

```bash
git commit -m "Nyaya Saathi: AI legal-help assistant (Kuku assignment, Problem 2)"
```

## 2. GitHub (for the submission form)

1. Create an **empty public** repo at https://github.com/new, e.g. `nyaya-saathi`. Don't add a README; the project already has one.
2. Push:

```bash
git remote add origin https://github.com/<your-username>/nyaya-saathi.git
```

```bash
git push -u origin main
```

GitHub will show the settings block at the top of `README.md` as a small table. That's expected; Hugging Face needs it.

## 3. Hugging Face Space (the live app)

1. Sign up at https://huggingface.co and subscribe to PRO at https://huggingface.co/pricing. Docker Spaces can't be created on a free account.
2. Go to https://huggingface.co/new-space and set:
   - **Space name:** `nyaya-saathi`
   - **SDK:** Docker → **Blank**
   - **Hardware:** CPU Basic (the free hardware tier)
   - **Visibility:** Public, so the reviewers can open it.
3. In the new Space, open **Settings → Variables and secrets** and add:

   | Name | Type | Value |
   |---|---|---|
   | `LLM_API_KEY` | **Secret** | your Gemini key (use a fresh one; see below) |
   | `LLM_PROVIDER` | Variable | `gemini` |
   | `LLM_MODEL` | Variable | `gemini-3.5-flash` |
   | `LLM_REASONING_EFFORT` | Variable | `low` |
   | `LLM_FALLBACK_MODELS` | Variable | `gemini-2.5-flash,gemini-3.1-flash-lite` |

4. Create a **write** access token at https://huggingface.co/settings/tokens. Git will use it as your password.
5. Push the same repo to the Space:

```bash
git remote add space https://huggingface.co/spaces/<your-hf-username>/nyaya-saathi
```

```bash
git push space main
```

When git asks for a password, paste the HF token.

6. Watch the **Logs** tab on the Space page. When it shows `You can now view your Streamlit app`, the app is live at `https://huggingface.co/spaces/<your-hf-username>/nyaya-saathi`.

To update the app later: commit, then `git push space main`. To update GitHub: `git push origin main`.

## 4. Before you submit

- **Use a new Gemini key.** The current one was pasted into a chat. Create a fresh key at https://aistudio.google.com, put it in the Space secret, and delete the old key.
- Open the Space link in a private browser window, to check it opens for anyone.
- Ask one example question. If every model is rate-limited, the app says so; the free quota resets daily.
- A Space on free hardware **goes to sleep when unused**. The first visit after that takes a while to wake it. Open it shortly before your interview.

## If something goes wrong

| Symptom | Fix |
|---|---|
| Build fails at `pip install` | Look at the Logs tab. If a pinned version is unavailable on Linux, relax that line in `requirements.txt` (e.g. `streamlit>=1.48`). |
| "No AI model configured" banner | A secret/variable is missing or misnamed (names are case-sensitive). Restart the Space after adding it. |
| "Free AI quota is used up" | Wait (quota resets daily), or add another fallback model or provider key. |
| Hugging Face rejects files over 10 MB | The index in `data/index/` is now over 10 MB, and the Docker build doesn't need it. Leave it out of the Space's copy of the repo, or track it with `git xet install`. |
| Search results look out of date | The index is committed for hosts that don't build it. After changing the Acts, run `python scripts/build_index.py` and commit `data/index/`. |
| App works locally but not on the Space | Check that `data/processed/sections.jsonl` was pushed: the index is built from it. |

## Run the same image locally (optional, needs Docker)

```bash
docker build -t nyaya-saathi .
```

```bash
docker run -p 7860:7860 --env-file .env nyaya-saathi
```

Then open http://localhost:7860.
