"""Radiance Grid-based Analysis Recipe."""

from ._gridbasedbase import GenericGridBased
from ..parameters.gridbased import LowQuality
from ..command.oconv import Oconv
from ..command.rtrace import Rtrace
from ..command.rcalc import Rcalc
from ...futil import writeToFile

from ladybug.dt import DateTime

import os


class GridBased(GenericGridBased):
    """Grid base analysis base class.

    Attributes:
        sky: A honeybee sky for the analysis
        analysisGrids: List of analysis grids.
        simulationType: 0: Illuminance(lux), 1: Radiation (kWh), 2: Luminance (Candela)
            (Default: 0)
        radParameters: Radiance parameters for grid based analysis (rtrace).
            (Default: gridbased.LowQuality)
        hbObjects: An optional list of Honeybee surfaces or zones (Default: None).
        subFolder: Analysis subfolder for this recipe. (Default: "gridbased")

    Usage:
        # create the sky
        sky = SkyWithCertainIlluminanceLevel(2000)

        # initiate analysisRecipe
        analysisRecipe = GridBased(
            sky, testPoints, ptsVectors, simType
            )

        # add honeybee object
        analysisRecipe.hbObjects = HBObjs

        # write analysis files to local drive
        analysisRecipe.write(_folder_, _name_)

        # run the analysis
        analysisRecipe.run(debaug=False)

        # get the results
        print analysisRecipe.results()
    """

    # TODO: implemnt isChanged at AnalysisRecipe level to reload the results
    # if there has been no changes in inputs.
    def __init__(self, sky, analysisGrids, simulationType=0, radParameters=None,
                 hbObjects=None, subFolder="gridbased"):
        """Create grid-based recipe."""
        GenericGridBased.__init__(
            self, analysisGrids, hbObjects, subFolder)

        self.sky = sky
        """A honeybee sky for the analysis."""

        self.radianceParameters = radParameters
        """Radiance parameters for grid based analysis (rtrace).
            (Default: gridbased.LowQuality)"""

        self.simulationType = simulationType
        """Simulation type: 0: Illuminance(lux), 1: Radiation (kWh),
           2: Luminance (Candela) (Default: 0)
        """

    @classmethod
    def fromPointsAndVectors(cls, sky, pointGroups, vectorGroups=None,
                             simulationType=0, radParameters=None,
                             hbObjects=None, subFolder="gridbased"):
        """Create grid based recipe from points and vectors.

        Args:
            sky: A honeybee sky for the analysis
            pointGroups: A list of (x, y, z) test points or lists of (x, y, z)
                test points. Each list of test points will be converted to a
                TestPointGroup. If testPts is a single flattened list only one
                TestPointGroup will be created.
            vectorGroups: An optional list of (x, y, z) vectors. Each vector
                represents direction of corresponding point in testPts. If the
                vector is not provided (0, 0, 1) will be assigned.
            simulationType: 0: Illuminance(lux), 1: Radiation (kWh), 2: Luminance
                (Candela) (Default: 0).
            radParameters: Radiance parameters for grid based analysis (rtrace).
                (Default: gridbased.LowQuality)
            hbObjects: An optional list of Honeybee surfaces or zones (Default: None).
            subFolder: Analysis subfolder for this recipe. (Default: "gridbased")
        """
        analysisGrids = cls.analysisGridsFromPointsAndVectors(pointGroups,
                                                              vectorGroups)
        return cls(sky, analysisGrids, simulationType, radParameters, hbObjects,
                   subFolder)

    @property
    def simulationType(self):
        """Get/set simulation Type.

        0: Illuminance(lux), 1: Radiation (kWh), 2: Luminance (Candela) (Default: 0)
        """
        return self.__simType

    @simulationType.setter
    def simulationType(self, value):
        try:
            value = int(value)
        except TypeError:
            value = 0

        assert 0 <= value <= 2, \
            "Simulation type should be between 0-2. Current value: {}".format(value)

        # If this is a radiation analysis make sure the sky is climate-based
        if value == 1:
            assert self.sky.isClimateBased, \
                "The sky for radition analysis should be climate-based."

        self.__simType = value

    @property
    def sky(self):
        """Get and set sky definition."""
        return self.__sky

    @sky.setter
    def sky(self, newSky):
        assert hasattr(newSky, "isRadianceSky"), "%s is not a valid Honeybee sky." \
            % type(newSky)
        self.__sky = newSky

    @property
    def radianceParameters(self):
        """Get and set Radiance parameters."""
        return self.__radianceParameters

    @radianceParameters.setter
    def radianceParameters(self, radParameters):
        if not radParameters:
            radParameters = LowQuality()
        assert hasattr(radParameters, "isRadianceParameters"), \
            "%s is not a radiance parameters." % type(radParameters)
        self.__radianceParameters = radParameters

    def write(self, targetFolder, projectName='untitled', header=True):
        """Write analysis files to target folder.

        Files for a grid based analysis are:
            test points <projectName.pts>: List of analysis points.
            sky file <*.sky>: Radiance sky for this analysis.
            material file <*.mat>: Radiance materials. Will be empty if HBObjects
                is None.
            geometry file <*.rad>: Radiance geometries. Will be empty if HBObjects
                is None.
            sky file <*.sky>: Radiance sky for this analysis.
            batch file <*.bat>: An executable batch file which has the list of commands.
                oconve <*.sky> <projectName.mat> <projectName.rad> <additional radFiles>
                    > <projectName.oct>
                rtrace <radianceParameters> <projectName.oct> > <projectName.res>
            results file <*.res>: Results file once the analysis is over.

        Args:
            targetFolder: Path to parent folder. Files will be created under
                targetFolder/gridbased. use self.subFolder to change subfolder name.
            projectName: Name of this project as a string.

        Returns:
            Full path to command.bat
        """
        # 0.prepare target folder
        # create main folder targetFolder\projectName
        sceneFiles = super(
            GenericGridBased, self).populateSubFolders(
                targetFolder, projectName)

        # 1.write points
        pointsFile = self.writePointsToFile(sceneFiles.path, projectName)

        # 2.write sky file
        skyFile = self.sky.writeToFile(sceneFiles.path + '\\skies')

        # 3.write batch file
        self.commands = []

        if header:
            self.commands.append(self.header(sceneFiles.path))

        # # 4.1.prepare oconv
        octSceneFiles = [skyFile, sceneFiles.matFile, sceneFiles.geoFile] + \
            sceneFiles.sceneMatFiles + sceneFiles.sceneRadFiles + sceneFiles.sceneOctFiles

        oc = Oconv(projectName)
        oc.sceneFiles = tuple(self.relpath(f, sceneFiles.path)
                              for f in octSceneFiles)

        # # 4.2.prepare rtrace
        rt = Rtrace('results\\' + projectName,
                    simulationType=self.simulationType,
                    radianceParameters=self.radianceParameters)
        rt.radianceParameters.h = True
        rt.octreeFile = str(oc.outputFile)
        rt.pointsFile = self.relpath(pointsFile, sceneFiles.path)

        # # 4.3. add rcalc to convert rgb values to irradiance
        rc = Rcalc('results\\{}.ill'.format(projectName), str(rt.outputFile))

        if os.name == 'nt':
            rc.rcalcParameters.expression = '"$1=(0.265*$1+0.67*$2+0.065*$3)*179"'
        else:
            rc.rcalcParameters.expression = "'$1=(0.265*$1+0.67*$2+0.065*$3)*179'"

        # # 4.4 write batch file
        self.commands.append(oc.toRadString())
        self.commands.append(rt.toRadString())
        self.commands.append(rc.toRadString())

        batchFile = os.path.join(sceneFiles.path, "commands.bat")

        writeToFile(batchFile, "\n".join(self.commands))

        self.resultsFile = os.path.join(sceneFiles.path, str(rc.outputFile))

        print "Files are written to: %s" % sceneFiles.path
        return batchFile

    def results(self, flattenResults=True):
        """Return results for this analysis."""
        assert self.isCalculated, \
            "You haven't run the Recipe yet. Use self.run " + \
            "to run the analysis before loading the results."

        sky = self.sky
        dt = DateTime(sky.month, sky.day, int(sky.hour),
                      int(60 * (sky.hour - int(sky.hour))))

        rf = self.resultsFile
        startLine = 0
        for count, analysisGrid in enumerate(self.analysisGrids):
            if count:
                startLine += len(self.analysisGrids[count - 1])

            analysisGrid.setValuesFromFile(
                rf, (int(dt.hoy),), startLine=startLine, header=False
            )

        return self.analysisGrids

    def ToString(self):
        """Overwrite .NET ToString method."""
        return self.__repr__()

    def __repr__(self):
        """Represent grid based recipe."""
        _analysisType = {
            0: "Illuminance", 1: "Radiation", 2: "Luminance"
        }
        return "%s: %s\n#PointGroups: %d #Points: %d" % \
            (self.__class__.__name__,
             _analysisType[self.simulationType],
             self.numOfAnalysisGrids,
             self.numOfTotalPoints)
