Introduction
===============

Localisation Helper is a python based tool for extracting localisable text from .m files within an XCode Project.

Localisation Harvester
 * Scans all .m files in the selected location to extract all text localised using the standard macros
 * Loads any existing localisation from the .strings files
 * Creates new .strings files for any new tables
 * Adds, updates or removes entries from string tables based on commandline options

Requirements
===============

Localisation Helper requires Python. I have tested it with Python v2.7.x on OS X 10.9 through 10.9

Usage
===============

##python LocalisationHelper -i <Input Folder> -o <Output Folder> [-r] [-mi|-mo|-mb|-mf] [-v]
    Input Folder   Base location to search for files with localisable text
    Output Folder  Output location for the localised .strings files
    -r             Add to recursively search through subfolders [default is non-recursive]
    -mi            Merge with existing files by only adding new text [default]
    -mo            Overwrite all existing localisation
    -mo            Overwrite all existing localisation
    -mf            Full merge with existing files. Adds new entries. 
                   Updates entries with different comments. Remove unreferenced keys.
    -v             Verbose mode [default is non-verbose]

Examples
===============

Generate the localisation for all .m files in the *~/Documents/TestApp* folder and subfolders.

    python LocalisationHelper.py -r -i ~/Documents/TestApp/ -o ~/Documents/TestApp/TestApp/en.lproj -mf
    
    # All text will be output to the *~/Documents/TestApp/TestApp/en.lproj* folder.
    # Full merging is enabled. Addition, Update and Deletion of localisation are permitted.