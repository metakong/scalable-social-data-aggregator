from __future__ import annotations
import json, re
import time
import os, shutil, subprocess
from typing import Any
from .models import AppIdea, IdeaStatus

def _generate_app_description(idea: AppIdea) -> str:

    """
    Generates a detailed app description suitable for a code generation prompt.
    """
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')  # Or another suitable model

        # Define an improved prompt for Gemini to generate a complete Android project
        prompt = f"""
        Act as an expert Android app developer. Your task is to generate the complete source code for a basic Android app based on the following description.
        The app should be written in Kotlin and use Jetpack Compose for the UI.  Use a modern, clean architecture with a single activity and appropriate composables for different screens.
        * Any other Kotlin files necessary for the app's functionality (e.g., composables for screens, data models, view models, etc.)

        Ensure the generated code is well-commented, follows Kotlin best practices, and is ready to be built and run.
        Include a Gradle wrapper in the project so it can be built with './gradlew assembleDebug'. Do not include any additional instructions or comments outside of the code blocks.
        """

        response = model.generate_content(prompt, request_options={'timeout': 120})  # Increased timeout

        if not response.text:
            raise ValueError("Gemini returned an empty response.")
        

    except (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable) as e:
        socketio.emit('log_message', {'data': f'[CTO WARNING] Gemini API error (rate limit or service issue): {e}'})
        raise e # Re-raise for Celery retry on transient errors
    except Exception as e:
        socketio.emit('log_message', {'data': f'[CTO FATAL] Code generation failed: {e}'})
        raise
        with open(filepath, "w") as f:
            f.write(content.strip())

def _build_apk(app_source_dir: str) -> str:
    """Builds an APK from the generated code using Gradle."""
    socketio.emit('log_message', {'data': '[CTO] Building APK with Gradle...'})
    try:
        # Basic validation: check for a build.gradle.kts file
        if not os.path.exists(os.path.join(app_source_dir, "app", "build.gradle.kts")):
            socketio.emit('log_message', {'data': '[CTO ERROR] No build.gradle.kts found. Is this a valid Android project?'})
            raise FileNotFoundError("build.gradle.kts not found in the generated project.")

        # 1. Run Gradle assembleDebug
        process = subprocess.run(
            ['./gradlew', 'assembleDebug'],
            cwd=os.path.join(app_source_dir, "app"),  # Assume Gradle wrapper is in the app subfolder
            capture_output=True,
            text=True
        )
        socketio.emit('log_message', {'data': f'[CTO] Gradle build output:\n{process.stdout}'})

        if process.returncode != 0:
            socketio.emit('log_message', {'data': f'[CTO ERROR] Gradle build failed:\n{process.stderr}'})
            raise RuntimeError(f"Gradle build failed with errors:\n{process.stderr}")

        # 2. Find the APK file (in the standard location)
        apk_path = Path(app_source_dir) / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
        if not apk_path.exists():
            raise FileNotFoundError(f"APK not found at expected location: {apk_path}")
        return str(apk_path)
    except subprocess.CalledProcessError as e:
        socketio.emit('log_message', {'data': f'[CTO ERROR] Gradle build command failed: {e}'})
        raise RuntimeError(f"Gradle build command failed: {e}") from e
    except FileNotFoundError as e:
        socketio.emit('log_message', {'data': f'[CTO ERROR] Gradle build setup issue: {e}'})
        raise
    except Exception as e:
        socketio.emit('log_message', {'data': f'[CTO FATAL] APK build process failed: {e}'})
        raise
