import csv
import whois
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
    """Check if a domain is available using whois"""
    try:
        w = whois.whois(domain)
        
        # Check multiple fields since whois responses can vary
        if w.domain_name is None and w.status is None and w.creation_date is None:
            return True
            
        # If domain_name is a list (some registrars return multiple values)
        if isinstance(w.domain_name, list):
            return False
            
        # Check status field
        if w.status is not None:
            return False
            
        # Check creation date
        if w.creation_date is not None:
            return False
            
        return True  # Only if all checks pass
        
    except Exception as e:
        print(f"Warning: Whois query error for {domain}: {str(e)}")
        return False  # Safer to assume domain is taken if query fails

def check_domains(csv_file):
    """Process keywords from CSV and check domain availability"""
    available_domains = []
    taken_domains = []
    uncertain_domains = []  # New list for potentially uncertain results
    
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header row
        
        for row in reader:
            if not row or not row[0]:  # Skip empty rows
                continue
                
            keyword = row[0]
            cleaned_keyword = clean_keyword(keyword)
            
            if not cleaned_keyword:
                continue
                
            domain = f"{cleaned_keyword}.com"
            
            print(f"Checking: {domain}")
            
            try:
                if is_domain_available(domain):
                    available_domains.append(domain)
                    print(f"Status: POTENTIALLY AVAILABLE (Verify on registrar)")
                else:
                    taken_domains.append(domain)
                    print(f"Status: TAKEN")
            except Exception as e:
                uncertain_domains.append(domain)
                print(f"Status: UNCERTAIN (Error occurred)")
                
            time.sleep(1)
    
    # Write results to files
    with open('available_domains_whois.txt', 'w') as f:
        f.write("IMPORTANT: Always verify availability with a domain registrar\n")
        f.write("These results are preliminary and may include false positives\n\n")
        f.write('\n'.join(available_domains))
        
    with open('taken_domains_whois.txt', 'w') as f:
        f.write('\n'.join(taken_domains))
        
    if uncertain_domains:
        with open('uncertain_domains_whois.txt', 'w') as f:
            f.write('\n'.join(uncertain_domains))
    
    print(f"\nResults:")
    print(f"Potentially available domains: {len(available_domains)}")
    print(f"Taken domains: {len(taken_domains)}")
    if uncertain_domains:
        print(f"Uncertain status: {len(uncertain_domains)}")
    print("\nIMPORTANT: Always verify domain availability with a registrar")
    print("These results are preliminary and may include false positives")
    print("\nResults have been saved to 'available_domains_whois.txt' and 'taken_domains_whois.txt'")

if __name__ == "__main__":
    csv_file = "main.csv"  # Path to your CSV file
    check_domains(csv_file) 