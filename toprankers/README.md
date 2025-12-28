# TopRankers Daily Automation

Automated processing of TopRankers daily current affairs pages to create both clean PDFs and Anki flashcards.

## Purpose

This folder contains scripts for automatically processing TopRankers daily current affairs:
1. **Generate Clean PDF** - Save to ~/saanvi/Legaledgedailygk/
2. **Generate Anki Cards** - Create flashcards and import to Anki

## Files

- `automate_html.sh` - Main automation script
- `extract_html.py` - HTML content extraction
- `generate_clean_pdf_final.py` - PDF generation with categorization
- `generate_flashcards_from_html.py` - Flashcard generation using Claude API
- `import_to_anki.py` - AnkiConnect integration
- `inbox/` - Temporary storage for intermediate JSON files

## Prerequisites

1. **Python Virtual Environment**: Uses shared `venv_clat` from parent directory
2. **Anthropic API Key**: Must be set in `~/.zshrc`
3. **Anki Running**: With AnkiConnect installed (code: 2055492159)

## Usage

### Process a TopRankers URL

```bash
cd /Users/arvind/clat_preparation/toprankers
source ~/.zshrc  # Load API key
./automate_html.sh https://www.toprankers.com/current-affairs-24th-december-2025
```

### With Custom Parameters

```bash
./automate_html.sh <url> [source] [week]
./automate_html.sh https://www.toprankers.com/current-affairs-24th-december-2025 toprankers 2025_Dec_D24
```

## Output

### PDF Output
- **Location**: `~/saanvi/Legaledgedailygk/current_affairs_YYYY_MONTH_DD.pdf`
- **Size**: ~20-25KB
- **Format**: A4, print-ready with orange category headers
- **Categories**: Automatically inferred (National, International, Environment, etc.)

### Anki Cards
- **Count**: 30-80 cards per day
- **Decks**: Distributed across 8 CLAT GK decks
- **Tags**: `source:toprankers`, `week:YYYY_MMM_DD`, topic tags
- **Import**: Automatic via AnkiConnect

## Processing Time

- **PDF Generation**: 3-5 seconds
- **Anki Generation**: 60-90 seconds (Claude API call)
- **Total**: ~90-120 seconds

## Integration

This folder replaces the old `/Users/arvind/Desktop/anki_automation/` location.

### Old Location (Deprecated)
- `/Users/arvind/Desktop/anki_automation/`

### New Location (Current)
- `/Users/arvind/clat_preparation/toprankers/`

## Dependencies

All dependencies are installed in the shared `venv_clat` virtual environment:
- anthropic
- beautifulsoup4
- requests
- reportlab
- python-dotenv

## Troubleshooting

### API Key Not Found
```bash
source ~/.zshrc
echo $ANTHROPIC_API_KEY  # Should show your key
```

### Anki Import Failed
1. Make sure Anki is running
2. Check AnkiConnect is installed
3. Close any dialog boxes in Anki

### Virtual Environment Issues
```bash
cd /Users/arvind/clat_preparation
source venv_clat/bin/activate
pip install -r toprankers/requirements.txt
```

## Notes

- This automation is triggered by the `toprankers-daily-automation` skill in Claude Code
- The scripts use the same virtual environment as the main CLAT preparation system
- PDFs are saved to the shared `~/saanvi/` directory structure
- All paths use `Path.home()` for cross-machine compatibility
