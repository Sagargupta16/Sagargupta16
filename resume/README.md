# Resume Management (Simplified)

This folder manages your resume with a simple upload flow.

## Structure

- `upload/` — Drop your latest resume PDF here. The workflow will pick it up.
- `versions/` — All versioned resume files live here (sagar-resume-vX.Y.Z.pdf).
- `VERSIONS.md` — Version history and rules.

At the repository root, the file `sagar_resume.pdf` is always the latest version.

## How it works

1. Commit a new PDF to `resume/upload/` (any name, .pdf extension).
2. Push to `main`.
3. GitHub Action will:
	- Decide bump type from your commit message ([major]/[minor]/patch default)
	- Create a new `sagar-resume-vX.Y.Z.pdf` in `resume/versions/`
	- Copy the uploaded PDF to the repository root as `sagar_resume.pdf`
	- Update `VERSIONS.md` (latest + history row)

## Examples

```powershell
# Add a minor update
Copy-Item ".\my-updated-resume.pdf" ".\resume\upload\my-updated-resume.pdf"
git add .
git commit -m "Add new project [minor]"
git push
```

After CI finishes, check:

- Root: `sagar_resume.pdf` (latest)
- `resume/versions/`: `sagar-resume-vX.Y.Z.pdf`
- `resume/VERSIONS.md`: updated
