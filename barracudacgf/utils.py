def print_header(title: str) -> None:
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")

def print_ok(msg: str) -> None:
    print(f"[+] {msg}")

def print_info(msg: str) -> None:
    print(f"[*] {msg}")

def print_err(msg: str) -> None:
    print(f"[!] {msg}")

def print_skip(msg: str) -> None:
    print(f"[~] {msg}")
