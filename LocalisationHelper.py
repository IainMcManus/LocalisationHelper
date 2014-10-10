#!/usr/bin/python

# Localisation Helper v0.1
# Copyright (c) 2013-2014 Iain McManus. All rights reserved.
#
# Localisation Helper parses all .m files in the selected path searching for
# the standard localisation macros. The localisation information from the macros is
# extracted and compared against the existing localisation files (if present).
#
# Depending on the selected merge options Localisation Helper can then add, update
# or remove entries from the existing localisation files. New localisation files are
# created if required.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import codecs, getopt, os, re, sys, subprocess

# InsertOnly - Existing localisation is not touched - only new localisations are added
# Overwrite - Existing localisation is purged - new localisations take priority
# MinimalMerge - Existing localisation retained if comment is unchanged. 
#              - If the comment is changed new localisation takes priority.
# FullMerge - Existing localisation retained if comment is unchanged. 
#           - If the comment is changed new localisation takes priority.
#           - Existing localisations that do not exist in the new localisation are purged
class MergeMode:
    InsertOnly, Overwrite, MinimalMerge, FullMerge = range(4)
    
class InputFileType:
    SourceCode, UserInterface = range(2)

# Builds up the list of all matching files
def buildFileList(inputDirectory, recursive):
        fileList = []

        if recursive:
                for root, folders, files in os.walk(inputDirectory):
                        for filename in files:
                                if filename.endswith('.m'):
                                        fileList.append([InputFileType.SourceCode, os.path.join(root, filename)])
                                elif filename.endswith('.xib'):
                                        fileList.append([InputFileType.UserInterface, os.path.join(root, filename)])
                                elif filename.endswith('.storyboard'):
                                        fileList.append([InputFileType.UserInterface, os.path.join(root, filename)])
        else:
                for filename in os.listdir(inputDirectory):
                        if filename.endswith('.m'):
                                fileList.append([InputFileType.SourceCode, os.path.join(inputDirectory, filename)]);
                        elif filename.endswith('.xib'):
                                fileList.append([InputFileType.UserInterface, os.path.join(inputDirectory, filename)]);
                        elif filename.endswith('.storyboard'):
                                fileList.append([InputFileType.UserInterface, os.path.join(inputDirectory, filename)]);

        return fileList

def performLocalisation(inputDirectory, outputDirectory, recursive, mergeType, verbose):
    filesToParse = buildFileList(inputDirectory, recursive)
    
    # Array of regular expressions to match against for extracting the localisable text.
    # Each array entry contains the following in order:
    #   - Compiled Regex
    #   - Index of the Key field if present (-1 otherwise)
    #   - Index of the Table Name field if present (-1 otherwise)
    #   - Index of the Comment if present (-1 otherwise)
    #   - Index of the Bundle if present (-1 otherwise)
    regexList = []
    regexList.append([re.compile('NSLocalizedStringFromTableInBundle\(@"([^"]*)",\s*@"([^"]*)",\s*([^,]*),\s*@"([^"]*)"\s*\)', re.DOTALL),  1,  2,  4, 3])
    regexList.append([re.compile('NSLocalizedStringFromTableInBundle\(@"([^"]*)",\s*@"([^"]*)",\s*([^,]*),\s*nil\s*\)', re.DOTALL),         1,  2, -1, 3])
    regexList.append([re.compile('NSLocalizedStringFromTable\(@"([^"]*)",\s*@"([^"]*)",\s*@"([^"]*)"\s*\)', re.DOTALL),  1,  2,  3, -1])
    regexList.append([re.compile('NSLocalizedStringFromTable\(@"([^"]*)",\s*@"([^"]*)",\s*nil\s*\)', re.DOTALL),         1,  2, -1, -1])
    regexList.append([re.compile('NSLocalizedString\(@"([^"]*)",\s*@"([^"]*)"\s*\)', re.DOTALL),                         1, -1,  2, -1])
    regexList.append([re.compile('NSLocalizedString\(@"([^"]*)",\s*nil\s*\)', re.DOTALL),                                1, -1, -1, -1])

    # Output set
    localisationTables = dict()
    
    processFailed = False
    errorMessage = ""
    
    # Localised data for the UI
    localisationData_UI = dict()

    # Process each file and extract the localised text entry
    for fileType, filePath in filesToParse:
        sourceFile = open(filePath, 'r')
        sourceFileContents = sourceFile.read()
        
        if fileType == InputFileType.SourceCode:
            for regex, keyPos, tablePos, commentPos, bundlePos in regexList:
                for result in regex.finditer(sourceFileContents):
                    locKey = result.group(keyPos)
                    locTable = 'Localizable'
                    locComment = ''
                
                    if tablePos > 0:
                        locTable = result.group(tablePos)
                    if commentPos > 0:
                        locComment = result.group(commentPos)
                
                    if locTable in localisationTables:
                        if locKey in localisationTables[locTable]:
                            [existingValue, existingComment] = localisationTables[locTable][locKey]
                        
                            if existingComment != locComment:
                                processFailed = True
                                errorMessage = "Key %s exists with different comments (%s and %s)" % (locKey, existingComment, locComment)
                        else:
                            localisationTables[locTable][locKey] = [locComment, locComment]
                    else:
                        localisationTables[locTable] = dict()
                        localisationTables[locTable][locKey] = [locComment, locComment]
                    
                    if processFailed:
                        break
                    
                if processFailed:
                    break
                
            if processFailed:
                break
        elif fileType == InputFileType.UserInterface:
            # run ibtool to extract the base UI localisation strings
            outputFileName = os.path.join(outputDirectory, "UI_%s.strings" % os.path.splitext(os.path.basename(filePath))[0])
            command = "ibtool --export-strings-file \"{outputFileName}\" \"{filePath}\"".format(outputFileName=outputFileName, filePath=filePath)
            commandOutput = subprocess.check_output(command, shell=True)
            
            generatedUIStrings = loadExistingStrings(outputFileName)
            
            # merge the localisation
            numNew, numUpdated, numRemoved, combinedLocalisation = unifyLocalisation(localisationData_UI, generatedUIStrings, MergeMode.InsertOnly)
            
            # delete the temporary file
            os.remove(outputFileName)
    
    if processFailed:
        print errorMessage
    else:
        totalNew = 0
        totalUpdated = 0
        totalRemoved = 0
        
        UILocalisationFileName = os.path.join(outputDirectory, "UI_Autogenerated.strings")

        # if the UI localisation already exists then load the file      
        existingUILocalisation = dict()
        if os.path.exists(UILocalisationFileName):
            existingUILocalisation = loadExistingStrings(UILocalisationFileName)
        
        # merge the existing and new UI localisation
        numNew, numUpdated, numRemoved, combinedUILocalisation = unifyLocalisation(existingUILocalisation, localisationData_UI, mergeType)
            
        # output the summary if we're in verbose mode
        if verbose:
            print "%s:" % UILocalisationFileName
            if numNew == 0 and numUpdated == 0 and numRemoved == 0:
                print "    No changes made"
            if numNew > 0:
                print "    %d entries added" % numNew
            if numUpdated > 0:
                print "    %d entries updated" % numUpdated
            if numRemoved > 0:
                print "    %d entries removed" % numRemoved
        
        # update the totals
        totalNew += numNew
        totalUpdated += numUpdated
        totalRemoved += numRemoved
            
        # write out the new UI localisation file
        writeLocalisedFile(UILocalisationFileName, combinedUILocalisation)
        
        # write out the individual localisation tables
        for tableName in localisationTables.keys():
            localisedFileName = os.path.join(outputDirectory, "%s.strings" % tableName)
            
            # load the existing localisation if present
            existingLocalisation = dict()
            if os.path.exists(localisedFileName):
                existingLocalisation = loadExistingStrings(localisedFileName)
            
            newLocalisation = localisationTables[tableName]
            
            # unify the old and new localisation tables
            numNew, numUpdated, numRemoved, combinedLocalisation = unifyLocalisation(existingLocalisation, newLocalisation, mergeType)
            
            # output the summary if we're in verbose mode
            if verbose:
                print "%s:" % localisedFileName
                if numNew == 0 and numUpdated == 0 and numRemoved == 0:
                    print "    No changes made"
                if numNew > 0:
                    print "    %d entries added" % numNew
                if numUpdated > 0:
                    print "    %d entries updated" % numUpdated
                if numRemoved > 0:
                    print "    %d entries removed" % numRemoved
            
            # update the totals
            totalNew += numNew
            totalUpdated += numUpdated
            totalRemoved += numRemoved
            
            # write out the localised file
            writeLocalisedFile(localisedFileName, combinedLocalisation)
        
        print ""
        print "Summary"
        if totalNew == 0 and totalUpdated == 0 and totalRemoved == 0:
            print "    No changes made"
        if totalNew > 0:
            print "    %d entries added" % totalNew
        if totalUpdated > 0:
            print "    %d entries updated" % totalUpdated
        if totalRemoved > 0:
            print "    %d entries removed" % totalRemoved

def writeLocalisedFile(localisedFileName, combinedLocalisation):
    # open and overwrite the existing file
    localisedFile = codecs.open(localisedFileName, "w", encoding='utf-16')
    
    # grab the keys and sort in ascending order
    localisedKeys = combinedLocalisation.keys()
    localisedKeys.sort()

    # write out the localised file
    for key in localisedKeys:
        value, comment = combinedLocalisation[key]
    
        localisedFile.write("/* %s */" % comment)
        localisedFile.write(os.linesep)
        
        localisedFile.write("\"%s\" = \"%s\";" % (key, value))
        localisedFile.write(os.linesep)
        
        localisedFile.write(os.linesep)

    localisedFile.close()

def unifyLocalisation(existingLocalisation, newLocalisation, mergeType):
    numNew = 0
    numUpdated = 0
    numRemoved = 0

    # Overwrite - easy option - just return the new localisation
    if mergeType == MergeMode.Overwrite:
        # determine the counts for new and updated
        for key in newLocalisation:
            if key in existingLocalisation:
                numUpdated += 1
            else:
                numNew += 1
                
        # determine the number removed
        for key in existingLocalisation:
            if key not in newLocalisation:
                numRemoved += 1
        
        return [numNew, numUpdated, numRemoved, newLocalisation]
            
    # For all other modes we start with the existing localisation as a base
    combinedLocalisation = existingLocalisation

    # Add new keys
    if mergeType in (MergeMode.InsertOnly, MergeMode.MinimalMerge, MergeMode.FullMerge):    
        for key in newLocalisation.keys():
            if key not in combinedLocalisation:
                combinedLocalisation[key] = newLocalisation[key]
                numNew += 1
    
    # Update existing keys if the comment changed
    if mergeType in (MergeMode.MinimalMerge, MergeMode.FullMerge):
        for key in newLocalisation.keys():
            if key in combinedLocalisation:
                currentValue, currentComment = combinedLocalisation[key]
                newValue, newComment = newLocalisation[key]
                
                if currentComment != newComment:
                    combinedLocalisation[key] = [newValue, newComment]
                    numUpdated += 1
    
    # Remove existing keys no longer referenced
    if mergeType == MergeMode.FullMerge:
        for key in combinedLocalisation.keys():
            if key not in newLocalisation:
                del combinedLocalisation[key]
                numRemoved += 1
    
    return [numNew, numUpdated, numRemoved, combinedLocalisation]

def loadExistingStrings(localisedFileName):
    localisedFile = codecs.open(localisedFileName, "r", encoding='utf-16')
    localisedFileContents = localisedFile.read()

    # extract all of the comments
    comments = []
    commentRegex = re.compile('/\*([^\*]*)', re.DOTALL)
    for commentIter in commentRegex.finditer(localisedFileContents):
        comment = commentIter.group(1)
        if len(comment) > 2:
            comments.append(comment[1:-1])
        else:
            comments.append(comment.strip())

    #extract all of the entries
    localisedEntries = []
    localisedEntryRegex = re.compile('"([^"]*)"\s=\s*"([^"]*)";', re.DOTALL)
    for entryIter in localisedEntryRegex.finditer(localisedFileContents):
        localisedEntries.append([entryIter.group(1), entryIter.group(2)])
    
    localisedFile.close()
    
    existingLocalisation = dict()
    
    # combine the comments and entries
    for entryIndex in range(0, len(comments)):
        key = localisedEntries[entryIndex][0]
        value = localisedEntries[entryIndex][1]
        description = comments[entryIndex];
        
        existingLocalisation[key] = [value, description]
        
    return existingLocalisation

def usage():
    print "Usage:"
    print "      LocalisationHelper -i <Input Folder> -o <Output Folder> [-r] [-mi|-mo|-mb|-mf] [-v]"
    print ""
    print "          Input Folder   Base location to search for files with localisable text"
    print "          Output Folder  Output location for the localised .strings files"
    print "          -r             Add to recursively search through subfolders [default is non-recursive]"
    print "          -mi            Merge with existing files by only adding new text [default]"
    print "          -mo            Overwrite all existing localisation"
    print "          -mb            Merge with existing files. Adds new entries and updates entries with different comments."
    print "          -mf            Full merge with existing files. Adds new entries. Updates entries with different comments. Remove unreferenced keys."
    print "          -v             Verbose mode [default is non-verbose]"

def main(argv):
    print "Localisation Helper for Xcode v0.1"
    print "Written by Iain McManus"
    print ""
    print "Copyright (c) 2013-2014 Iain McManus. All rights reserved"
    print ""
    
    inputDirectory = os.getcwd()
    outputDirectory = os.getcwd()
    recursive = False
    mergeType = MergeMode.InsertOnly
    essentialArgumentsFoundCount = 0
    verbose = False
    
    # parse the arguments
    try:
        opts, args = getopt.getopt(argv, "hrvm:i:o:", ["help", "recursive", "verbose", "merge=", "input=", "output="])
    except getopt.GetoptError, exc:
        print exc.msg
        
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h"):
            usage()
            sys.exit()
        elif opt in ("-i"):
            inputDirectory = arg
            essentialArgumentsFoundCount += 1
        elif opt in ("-o"):
            outputDirectory = arg
            essentialArgumentsFoundCount += 1
        elif opt in ("-r"):
            recursive = True
        elif opt in ("-m"):
            if arg in ("-i"):
                mergeType = MergeMode.InsertOnly
            elif arg in ("-o"):
                mergeType = MergeMode.Overwrite
            elif arg in ("-b"):
                mergeType = MergeMode.MinimalMerge
            elif arg in ("-f"):
                mergeType = MergeMode.FullMerge
        elif opt in ("-v"):
            verbose = True

    if essentialArgumentsFoundCount < 2:
        usage()
        sys.exit(2)

    performLocalisation(inputDirectory, outputDirectory, recursive, mergeType, verbose)

if __name__ == '__main__':
    main(sys.argv[1:])
