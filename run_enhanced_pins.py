#!/usr/bin/env python3
"""
Run Enhanced Pin Detection Analysis
"""

from src.enhanced_pin_detection.integration import initialize_enhanced_pin_detector, generate_pin_analysis

def main():
    print("🎯 Starting Enhanced Pin Detection Analysis...")
    initialize_enhanced_pin_detector()
    generate_pin_analysis()

if __name__ == "__main__":
    main()