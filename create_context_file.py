import os
import datetime

# --- Configuration ---
# The name of the output file that will be created.
OUTPUT_FILENAME = "project_context.txt"

# List of directories to completely ignore.
DIRECTORIES_TO_IGNORE = {
    ".git",
    ".vscode",
    ".idea",
    "__pycache__",
    "env",
    "venv",
    ".venv",
    "node_modules",
    "migrations", # We can see the schema in models.py
}

# List of specific files to ignore by name.
FILES_TO_IGNORE = {
    ".DS_Store",
    ".gitignore",
    ".dockerignore",
    ".env",
    "tfplan",
    ".terraform.lock.hcl",
    OUTPUT_FILENAME,  # Ignore the output file itself
    "create_context_file.py" # Ignore this script file
}

# List of file extensions to ignore (e.g., binary files).
EXTENSIONS_TO_IGNORE = {
    ".pyc", ".pyo", ".pyd", ".swp", ".swo", # Python cache/swap
    ".ico", ".png", ".jpg", ".jpeg", ".gif", # Images
    ".zip", ".tar", ".gz", # Archives
    ".pdf", ".docx", ".xlsx", # Documents
}
# --- End Configuration ---

def should_ignore(path: str, is_dir: bool) -> bool:
    """Checks if a given file or directory should be ignored."""
    basename = os.path.basename(path)
    
    if is_dir:
        return basename in DIRECTORIES_TO_IGNORE
    
    if basename in FILES_TO_IGNORE:
        return True
        
    if any(path.endswith(ext) for ext in EXTENSIONS_TO_IGNORE):
        return True
        
    return False

def generate_context_file():
    """Walks the project directory and writes file contents to a single output file."""
    project_root = os.getcwd()
    file_count = 0
    
    print(f"Starting context generation in root directory: {project_root}")
    
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as outfile:
        # Write a header to the file
        outfile.write(f"Project Context for Veiled Vector Space\n")
        outfile.write(f"Generated on: {datetime.datetime.now().isoformat()}\n")
        outfile.write("=" * 80 + "\n\n")

        for root, dirs, files in os.walk(project_root, topdown=True):
            # Modify dirs in-place to prevent os.walk from descending into ignored directories
            dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), True)]

            for filename in sorted(files):
                file_path = os.path.join(root, filename)
                
                if should_ignore(file_path, False):
                    continue

                relative_path = os.path.relpath(file_path, project_root)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        content = infile.read()
                        
                        outfile.write(f"--- File: {relative_path} ---\n\n")
                        outfile.write(content)
                        outfile.write("\n\n" + "=" * 80 + "\n\n")
                        file_count += 1
                        print(f"  + Added: {relative_path}")
                        
                except UnicodeDecodeError:
                    print(f"  ! Skipped (not a text file): {relative_path}")
                except Exception as e:
                    print(f"  ! Error reading {relative_path}: {e}")

    print(f"\nContext generation complete.")
    print(f"Added {file_count} files to '{OUTPUT_FILENAME}'.")

if __name__ == "__main__":
    generate_context_file()