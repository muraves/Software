def Search_File(string):
    import glob

    fileName = glob.glob(string+'*')

    if len(fileName)>0:
        return str(fileName[0])
    else:
        return("NOTaFIle")
                

        
        
