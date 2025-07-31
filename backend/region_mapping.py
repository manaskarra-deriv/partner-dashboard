"""
Hardcoded region to country mapping for GP regions
This ensures consistent and accurate region aggregation
"""

REGION_COUNTRY_MAPPING = {
    "Africa - FR": [
        "Benin", "Burkina Faso", "Burundi", "Cameroon", "Central African Republic", 
        "Chad", "Comoros", "Congo", "Côte d'Ivoire", "Djibouti", "Equatorial Guinea", 
        "Gabon", "Guinea", "Madagascar", "Mali", "Mauritania", "Niger", "Senegal", "Togo"
    ],
    
    "Africa - PT": [
        "Angola", "Guinea-Bissau", "Mozambique", "Sao Tome and Principe"
    ],
    
    "Africa EN (Eastern)": [
        "Eritrea", "Ethiopia", "Kenya", "Mauritius", "Rwanda", "Seychelles", 
        "Somalia", "South Sudan", "Sudan", "Tanzania", "Uganda"
    ],
    
    "Africa EN (Southern)": [
        "Botswana", "Eswatini", "Lesotho", "Malawi", "Namibia", "South Africa", 
        "Zambia", "Zimbabwe"
    ],
    
    "Africa EN (Western)": [
        "Gambia", "Ghana", "Liberia", "Nigeria", "Sierra Leone"
    ],
    
    "Americas": [
        "Canada", "United States"
    ],
    
    "Asia - ISC": [
        "Bangladesh", "Bhutan", "India", "Iran", "Maldives", "Nepal", "Pakistan", "Sri Lanka"
    ],
    
    "Asia - SEA": [
        "Brunei", "Cambodia", "China", "Hong Kong", "Indonesia", "Japan", "North Korea", 
        "South Korea", "Laos", "Macao", "Malaysia", "Mongolia", "Myanmar", "Philippines", 
        "Singapore", "Taiwan", "Thailand", "Timor-Leste", "Vietnam"
    ],
    
    "CIS": [
        "Armenia", "Azerbaijan", "Belarus", "Georgia", "Kazakhstan", "Kyrgyzstan", 
        "Tajikistan", "Turkmenistan", "Uzbekistan"
    ],
    
    "EU": [
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", 
        "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", 
        "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", 
        "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"
    ],
    
    "LATAM - Central America": [
        "Antigua and Barbuda", "Bahamas", "Barbados", "Belize", "Costa Rica", "Cuba", 
        "Dominica", "Dominican Republic", "El Salvador", "Grenada", "Guatemala", "Haiti", 
        "Honduras", "Jamaica", "Mexico", "Nicaragua", "Panama", "Puerto Rico", 
        "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", 
        "Trinidad and Tobago", "Turks and Caicos Islands", "British Virgin Islands", 
        "U.S. Virgin Islands"
    ],
    
    "LATAM - Colombia": [
        "Colombia"
    ],
    
    "LATAM - PT": [
        "Portugal"
    ],
    
    "LATAM - South America": [
        "Argentina", "Bolivia", "Brazil", "Chile", "Ecuador", "Guyana", "Paraguay", 
        "Peru", "Suriname", "Uruguay", "Venezuela"
    ],
    
    "MENA - AR": [
        "Algeria", "Bahrain", "Egypt", "Iraq", "Israel", "Jordan", "Kuwait", "Lebanon", 
        "Libya", "Morocco", "Oman", "Palestine", "Qatar", "Saudi Arabia", "Syria", 
        "Tunisia", "UAE", "Western Sahara", "Yemen"
    ],
    
    "Oceania": [
        "Australia", "New Zealand", "Fiji", "Papua New Guinea", "Samoa", "Tonga", 
        "Vanuatu", "Kiribati", "Micronesia", "Marshall Islands", "Palau", "Tuvalu", 
        "Nauru", "Tokelau", "Niue", "Norfolk Island"
    ],
    
    "Rest of Europe": [
        "Albania", "Andorra", "Aruba", "Bermuda", "Bosnia and Herzegovina", "Curaçao", 
        "Faroe Islands", "Gibraltar", "Greenland", "Guernsey", "Iceland", "Isle of Man", 
        "Jersey", "Liechtenstein", "Monaco", "Montenegro", "North Macedonia", "Norway", 
        "San Marino", "Serbia", "Switzerland", "Turkey", "United Kingdom"
    ]
}

def get_countries_for_region(region_name):
    """Get list of countries for a given region"""
    return REGION_COUNTRY_MAPPING.get(region_name, [])

def get_all_regions():
    """Get list of all available regions"""
    return list(REGION_COUNTRY_MAPPING.keys())

def get_region_for_country(country_name):
    """Get the region for a given country"""
    for region, countries in REGION_COUNTRY_MAPPING.items():
        if country_name in countries:
            return region
    return None