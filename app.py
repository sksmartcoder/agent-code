#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from agent_core.master_agent import MasterAgent

def main():
    description = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter ticket description: ").strip()
    if not description:
        print("Error: description cannot be empty.")
        sys.exit(1)
    result = MasterAgent().process(description)
    print(f"\nDone. Ticket: {result.get('ticket_id')} | Status: {result.get('final_status')}")

if __name__ == "__main__":
    main()
