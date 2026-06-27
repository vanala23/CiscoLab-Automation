import subprocess
import sys
import os

MODULES = {
    "1": ("Barracuda CGF", "barracudacgf"),
}

def main():
    print("\n" + "="*50)
    print("  CiscoLab Automation")
    print("="*50)

    for key, (name, _) in MODULES.items():
        print(f"  [{key}] {name}")

    print("\n  [q] Quit")
    choice = input("\nSelect: ").strip()

    if choice == "q":
        return

    if choice in MODULES:
        name, folder = MODULES[choice]
        print(f"\n-> Starting {name}...\n")
        subprocess.run(
            [sys.executable, "main.py"],
            cwd=os.path.join(os.path.dirname(__file__), folder)
        )
    else:
        print("Invalid selection")

if __name__ == "__main__":
    main()
