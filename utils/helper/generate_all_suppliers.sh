#!/bin/bash

# Generate JSON files for all suppliers
# Usage: ./generate_all_suppliers.sh [supplier_name|--all]

echo "🚀 Hotel Supplier JSON Generator"
echo "================================"

# Check if we're in the right directory
if [ ! -f "country_json_file.py" ]; then
    echo "❌ Error: country_json_file.py not found in current directory"
    echo "Please run this script from the utils/helper directory"
    exit 1
fi

# Check if Python environment is available
if ! command -v python &> /dev/null; then
    echo "❌ Error: Python not found. Please ensure Python is installed and in PATH"
    exit 1
fi

# Function to show usage
show_usage() {
    echo "Usage:"
    echo "  $0                    # Process default supplier (mgholiday)"
    echo "  $0 --all              # Process all suppliers"
    echo "  $0 <supplier_name>    # Process specific supplier"
    echo ""
    echo "Available suppliers:"
    echo "  hotelbeds, ean, agoda, mgholiday, restel, stuba,"
    echo "  hyperguestdirect, tbohotel, goglobal, ratehawkhotel,"
    echo "  grnconnect, juniperhotel, paximumhotel, oryxhotel,"
    echo "  dotw, hotelston, letsflyhotel, illusionshotel,"
    echo "  innstant, roomerang, mikihotel, adonishotel,"
    echo "  w2mhotel, kiwihotel, rakuten, rnrhotel"
}

# Check arguments
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_usage
    exit 0
fi

# Set start time
start_time=$(date +%s)

echo "⏰ Started at: $(date)"
echo ""

# Run the Python script with arguments
if [ $# -eq 0 ]; then
    echo "🔄 Processing default supplier..."
    python country_json_file.py
elif [ "$1" = "--all" ]; then
    echo "🔄 Processing ALL suppliers..."
    python country_json_file.py --all
else
    echo "🔄 Processing supplier: $1"
    python country_json_file.py "$1"
fi

# Calculate execution time
end_time=$(date +%s)
execution_time=$((end_time - start_time))

echo ""
echo "⏰ Completed at: $(date)"
echo "⌛ Total execution time: ${execution_time} seconds"

# Check if the script was successful
if [ $? -eq 0 ]; then
    echo "✅ Script completed successfully!"
else
    echo "❌ Script failed with errors!"
    exit 1
fi