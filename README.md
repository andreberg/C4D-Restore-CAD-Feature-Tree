Restore CAD Feature Tree
========================

Restore CAD Feature Tree is a command plugin that  
helps with restoring "feature tree" relationships  
found in CAD files. 

It requires the relationship information to be  
encoded into the names of the imported objects. 


Requirements
------------

CINEMA 4D R12 or later


Scenario
--------

Often times when you import "triangulated" models from  
a CAD package, the hierarchical relationships from the  
"feature tree" (think C4D's object manager which has a  
very similar purpose) get lost in translation. 

Like for example in CINEMA 4D you can make parametric  
objects editable and thus loose the ability to edit after  
the fact.

With some CAD packages however, information about these  
relationships gets encoded into the name strings of all  
exported submodels (called parts in CAD lingo) that comprise  
the complete model (the assembly in CAD terms), making it  
possible to restore the relationships/nestings and mirror  
them in CINEMA 4D's Object Manager. 


Modus Operandi
--------------

This Script does just that. It attempts to rebuild the lost  
information by parsing the object names of all imported objects. 

It was primarily made for a workflow from Pro/E (exported as STEP) to  
PunchCAD's [ViaCAD/SharkFX](http://www.punchcad.com/ "ViaCAD/SharkFX") from which to export as Wavefront OBJ.

ViaCAD produces excellent quality polygonal OBJ models and it encodes  
the relationship from the feature tree found in the STEP file into  
the model units it writes to the OBJ file.

For example, when this OBJ is imported into CINEMA 4D, one object  
might be named:

`A_762_82_001_37_ASM|Next assembly relationship#A_620_45_120_11_OPEN_AF0_ASM|Next assembly relationship#13_BCC_01_001_11_AF0;13_BCC_01_001_11_AF1`

from which a tree structure can be derived:

    A_762_82_001_37_ASM
       +- A_620_45_120_11_OPEN_AF0_ASM
          +- 13_BCC_01_001_11_AF0
          +- 13_BCC_01_001_11_AF1

Additionally there's a pre/post filtering system to clean up the  
object names before splitting and processing, as well as making  
sure there are no duplicates.

License
-------

    Created by André Berg on 2011-03-19.
    Copyright Berg Media 2013. All rights reserved.
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
      http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

