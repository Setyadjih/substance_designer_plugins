# Color Mixer Plugin
Substance Designer plugin to Colormatch a texture map into various chosen colors, pantone colors, or hue spectrum.

The plugin takes primarily takes advantage of the Colormatch node and the new Pantone Spot Colors in Substance designer. It's meant to act as a utility plugin to generate a spread of colors from a single texture map, for quick protype recoloring.


## Build
Run the `makepackage.py` within the plugin folders to package the plugins as an `.sdplugin`. 

## Installation
The `.sdplugin` file can be installed with the Substance Designer plugin manager. 

Alternatively, the plugin within the folder can be copy and pasted into the *Substance Designer plugin directory*. 
Make sure to close and reopen your graphs if you need to refresh your plugins.

## Usage
Select the desired Color map, and press the plugin icon. The plugin expects the **_COL** suffix, but it is not required.
