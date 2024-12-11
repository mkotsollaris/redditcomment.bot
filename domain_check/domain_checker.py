import csv
import socket
import time
from urllib.parse import quote

def clean_keyword(keyword):
    """Clean keyword to make it domain-friendly"""
    # Remove quotes and special characters, convert to lowercase
    cleaned = keyword.strip('"')  # Remove quotes
    cleaned = ''.join(c for c in cleaned if c.isalnum() or c == '-').lower()
    # Remove leading/trailing hyphens
    cleaned = cleaned.strip('-')
    return cleaned

def is_domain_available(domain):
    """Check if a domain is available by attempting a DNS lookup"""
    try:
        # Attempt to resolve the domain
        socket.gethostbyname(domain)
        return False  # Domain is taken
    except socket.gaierror:
        return True  # Domain is potentially available

def check_domains(csv_file):
    """Process keywords from CSV and check domain availability"""
    available_domains = []
    taken_domains = []
    
    with open(csv_file, 'r', encoding='utf-8') as file:
        # Use csv.reader instead of DictReader to handle quoted fields properly
        reader = csv.reader(file)
        next(reader)  # Skip header row
        
        for row in reader:
            if not row:  # Skip empty rows
                continue
                
            keyword = row[0]  # First column contains keywords
            cleaned_keyword = clean_keyword(keyword)
            
            if not cleaned_keyword:
                continue
                
            domain = f"{cleaned_keyword}.com"
            
            print(f"Checking: {domain}")
            
            if is_domain_available(domain):
                available_domains.append(domain)
                print(f"Status: AVAILABLE")
            else:
                taken_domains.append(domain)
                print(f"Status: TAKEN")
                
            # Add a small delay to avoid overwhelming DNS servers
            time.sleep(0.5)
    
    # Write results to files
    with open('available_domains.txt', 'w') as f:
        f.write('\n'.join(available_domains))
        
    with open('taken_domains.txt', 'w') as f:
        f.write('\n'.join(taken_domains))
    
    print(f"\nResults:")
    print(f"Available domains: {len(available_domains)}")
    print(f"Taken domains: {len(taken_domains)}")
    print("\nResults have been saved to 'available_domains.txt' and 'taken_domains.txt'")

if __name__ == "__main__":
    csv_file = "main.csv"  # Path to your CSV file
    check_domains(csv_file) 