from faker import Faker
from datetime import datetime, timedelta
import random
from typing import List, Dict
from app.models.leads import Lead, Address, Project

fake = Faker()

def generate_random_address() -> Dict:
    """Generate random address data"""
    return {
        'street': fake.street_address(),
        'city': fake.city(),
        'state': fake.state(),
        'postal_code': fake.postcode(),
        'country': fake.country()
    }

def generate_random_project() -> Dict:
    """Generate random project data"""
    start_date = fake.date_time_between(start_date='-1y', end_date='+30d')
    end_date = start_date + timedelta(days=random.randint(90, 365))
    
    return {
        'name': fake.catch_phrase(),
        'description': fake.text(max_nb_chars=200),
        'status': random.choice(['active', 'completed', 'on_hold', 'cancelled']),
        'location': fake.city(),
        'budget': random.randint(50000, 1000000),
        'start_date': start_date,
        'end_date': end_date
    }

def generate_random_lead(project_id: int, address_id: int) -> Dict:
    """Generate random lead data"""
    # Generate a shorter phone number format: XXX-XXX-XXXX
    phone = fake.numerify(text='###-###-####')
    
    return {
        'name': fake.name(),
        'email': fake.email(),
        'phone': phone,
        'status': random.choice(['new', 'contacted', 'qualified', 'proposal', 'negotiation', 'closed']),
        'source': random.choice(['website', 'referral', 'social_media', 'direct', 'partner']),
        'project_id': project_id,
        'address_id': address_id
    }

def generate_bulk_data(count: int = 10) -> List[Dict]:
    """Generate bulk random data for all models"""
    bulk_data = []
    
    for _ in range(count):
        # Generate address
        address_data = generate_random_address()
        address = Address(**address_data)
        
        # Generate project
        project_data = generate_random_project()
        project = Project(**project_data)
        
        # Generate lead
        lead_data = generate_random_lead(None, None)  # IDs will be set after insertion
        lead = Lead(**lead_data)
        
        bulk_data.append({
            'address': address,
            'project': project,
            'lead': lead
        })
    
    return bulk_data
