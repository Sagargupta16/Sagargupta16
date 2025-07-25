# Resume Version Management

## Current Structure
```
resume/
├── current/
│   ├── sagar_resume.pdf           # Latest version
│   ├── sagar_resume.tex           # LaTeX source (if applicable)
│   └── README.md                  # Version notes
├── versions/
│   ├── 2025/
│   │   ├── sagar_resume_v2025.1.pdf
│   │   ├── sagar_resume_v2025.2.pdf
│   │   └── version_notes.md
│   └── 2024/
│       ├── sagar_resume_v2024.1.pdf
│       └── sagar_resume_v2024.2.pdf
├── templates/
│   ├── software_engineer_focus.pdf
│   ├── data_scientist_focus.pdf
│   └── fullstack_developer_focus.pdf
└── CHANGELOG.md
```

## Naming Convention
- **Format**: `sagar_resume_vYYYY.M.pdf`
- **YYYY**: Year
- **M**: Major version within year
- **Example**: `sagar_resume_v2025.3.pdf`

## Git Tags for Releases
- `resume-v2025.1` - First version of 2025
- `resume-v2025.2` - Updated with new project
- `resume-latest` - Always points to current version
