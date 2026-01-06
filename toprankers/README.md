# TopRankers Daily PDF Generator

Automated processing of TopRankers daily current affairs pages to create clean PDFs.

## Purpose

This folder contains scripts for processing TopRankers daily current affairs:
- **Generate Clean PDF** - Save to ~/saanvi/Legaledgedailygk/

## Files

- `extract_html.py` - HTML content extraction
- `generate_clean_pdf_final.py` - PDF generation with categorization
- `inbox/` - Temporary storage for intermediate JSON files

## Prerequisites

1. **Python Virtual Environment**: Uses shared `venv_clat` from parent directory
2. **Anthropic API Key**: Must be set in `~/.zshrc`

## Usage

### Process a TopRankers URL

```bash
cd /Users/arvind/clat_preparation/toprankers
source ../venv_clat/bin/activate
python generate_clean_pdf_final.py https://www.toprankers.com/current-affairs-24th-december-2025
```

## Output

### PDF Output
- **Location**: `~/saanvi/Legaledgedailygk/current_affairs_YYYY_MONTH_DD.pdf`
- **Size**: ~20-25KB
- **Format**: A4, print-ready with orange category headers
- **Categories**: Automatically inferred (National, International, Environment, etc.)

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

### Virtual Environment Issues
```bash
cd /Users/arvind/clat_preparation
source venv_clat/bin/activate
pip install -r toprankers/requirements.txt
```

## Notes

- PDFs are saved to the shared `~/saanvi/` directory structure
- All paths use `Path.home()` for cross-machine compatibility
