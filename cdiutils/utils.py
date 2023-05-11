from typing import Optional, Tuple, Union, List
import numpy as np
import matplotlib
import seaborn as sns
from scipy.ndimage import convolve, center_of_mass  
from scipy.stats import gaussian_kde
import textwrap
import xrayutilities as xu

from cdiutils.plot.formatting import plot_background


def pretty_print(text: str, max_char_per_line: int=80) -> None:
    """Print text with a frame of stars."""

    stars = "*" * max_char_per_line
    print("\n" + stars)
    print("*", end="")
    for i in range((max_char_per_line-len(text))//2 - 1):
        print(" ", end="")
    print(textwrap.fill(text, max_char_per_line), end="")
    for i in range((max_char_per_line-len(text))//2 - 1 + len(text)%2):
        print(" ", end="")
    print("*")
    print(stars + "\n")


def size_up_support(support: np.ndarray) -> np.ndarray:
    kernel = np.ones(shape=(3, 3, 3))
    convolved_support = convolve(support, kernel, mode='constant', cval=0.0)
    return np.where(convolved_support > 3, 1, 0)

def find_hull(
        volume: np.ndarray,
        threshold: float=18,
        kernel_size: int=3,
        boolean_values: bool=False,
        nan_value: bool=False
) -> np.ndarray:
    """
    Find the convex hull of a 3D volume object.
    :param volume: 3D np.array. The volume to get the hull from.
    :param threshold: threshold that selects what belongs to the
    hull or not (int). If threshold >= 27, the returned hull will be
    similar to volume.
    :kernel_size: the size of the kernel used to convolute (int).
    :boolean_values: whether or not to return 1 and 0 np.ndarray
    or the computed coordination.

    :returns: the convex hull of the shape accordingly to the given
    threshold (np.array).
    """

    kernel = np.ones(shape=(kernel_size, kernel_size, kernel_size))
    convolved_support = convolve(volume, kernel, mode='constant', cval=0.0)
    hull = np.where(
        ((0 < convolved_support) & (convolved_support <= threshold)),
        1 if boolean_values else convolved_support,
        np.nan if nan_value else 0)
    return hull


def make_support(
        data: np.ndarray,
        isosurface: float=0.5,
        nan_values: bool=False
) -> np.ndarray:
    """Create a support using the provided isosurface value."""
    data = normalize(data)
    return np.where(data >= isosurface, 1, np.nan if nan_values else 0)


def unit_vector(
        vector: Union[tuple, list, np.ndarray]
)-> Union[tuple, list, np.ndarray]:
    """Return a unit vector."""
    return vector / np.linalg.norm(vector)


def angle(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute angle between two vectors."""
    return np.arccos(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


def v1_to_v2_rotation_matrix(
        v1: np.ndarray,
        v2: np.ndarray
) -> np.ndarray:
    """ 
    Rotation matrix around axis v1xv2
    """
    vec_rot_axis = np.cross(v1, v2)
    normed_vrot = unit_vector(vec_rot_axis)

    theta = angle(v1, v2)

    n1, n2, n3 = normed_vrot
    ct = np.cos(theta)
    st = np.sin(theta)

    r = np.array(((ct+n1**2*(1-ct), n1*n2*(1-ct)-n3*st, n1*n3*(1-ct)+n2*st),
                  (n1*n2*(1-ct)+n3*st, ct+n2**2*(1-ct), n2*n3*(1-ct)-n1*st),
                  (n1*n3*(1-ct)-n2*st, n2*n3*(1-ct)+n1*st, ct+n3**2*(1-ct))
                  ))
    return r


def normalize(
        data: np.ndarray,
        zero_centered: bool=False
) -> np.ndarray:
    """Normalize a np.ndarray so the values are between 0 and 1."""
    if zero_centered:
        abs_max = np.max([np.abs(np.min(data)), np.abs(np.max(data))])
        vmin, vmax = -abs_max, abs_max
        ptp = vmax - vmin
    else:
        ptp = np.ptp(data)
        vmin = np.min(data)
    return (data - vmin) / ptp

def basic_filter(data, maplog_min_value=3.5):
    return np.power(xu.maplog(data, maplog_min_value, 0), 10)

def normalize_complex_array(array: np.ndarray) -> np.ndarray:
    """Normalize a array of complex numbers."""
    shifted_array = array - array.real.min() - 1j*array.imag.min()
    return shifted_array/np.abs(shifted_array).max()


def find_max_pos(data: np.ndarray) -> tuple:
    """Find the index coordinates of the maximum value."""
    return np.unravel_index(data.argmax(), data.shape)


def shape_for_safe_centered_cropping(
        data_shape: Union[tuple, np.ndarray, list],
        position: Union[tuple, np.ndarray, list],
        final_shape: Optional[tuple]=None
) -> tuple:
    """
    Utility function that finds the smallest shape that allows a safe
    cropping, i.e. without moving data from one side to another when
    using the np.roll() function.
    """
    if not isinstance(data_shape, np.ndarray):
        data_shape = np.array(data_shape)
    if not isinstance(position, np.ndarray):
        position = np.array(position)

    secured_shape = 2 * np.min([position, data_shape - position], axis=0)
    secured_shape = tuple([round(e) for e in secured_shape])

    if final_shape is None:
        return tuple(secured_shape)
    else:
        return tuple(np.min([secured_shape, final_shape], axis=0))


def _center_at_com(data: np.ndarray):
    shape = data.shape
    com = tuple(e for e in center_of_mass(data))
    print((np.array(shape)/2 == np.array(com)).all())
    com_to_center = np.array([
        int(np.rint(shape[i]/2 - com[i]))
        for i in range(3)
    ])
    if (com_to_center == np.array((0, 0, 0)).astype(int)).all():
        return data, com
    data = center(data, where=com)
    return _center_at_com(data)


def center(
        data: np.ndarray,
        where: Union[str, tuple, list, np.ndarray]="com",
        return_former_center: bool=False
) -> Union[np.ndarray, Tuple[np.ndarray, tuple]]:
    """
    Center 3D volume data such that the center of mass or max  of data
    is at the very center of the 3D matrix.
    :param data: volume data (np.array). 3D numpy array which will be
    centered.
    :param com: center of mass coordinates(list, np.array). If no com is
    provided, com of the given data is computed (default: None).
    :param where: what region to place at the center (str), either
    com or max, or a tuple of the coordinates where to place the center
    at.
    :returns: centered 3D numpy array.
    """
    shape = data.shape

    if isinstance(where, (tuple, list, np.ndarray)) and len(where) == 3:
        reference_position = tuple(where)
    elif where == "max":
        reference_position = find_max_pos(data)
    elif where == "com":
        reference_position = tuple(e for e in center_of_mass(data))
    else:
        raise ValueError(
            "where must be 'max', 'com' or tuple or list of 3 floats "
            f"coordinates, can't be type: {type(where)} ({where}) "
        )
    xcenter, ycenter, zcenter = reference_position

    centered_data = np.roll(data, int(np.rint(shape[0] / 2 - xcenter)), axis=0)
    centered_data = np.roll(
        centered_data,
        int(np.rint(shape[1] / 2 - ycenter)),
        axis=1
    )
    centered_data = np.roll(
        centered_data,
        int(np.rint(shape[2] / 2 - zcenter)),
        axis=2
    )

    if return_former_center:
        return centered_data, (xcenter, ycenter, zcenter)

    return centered_data


def symmetric_pad(
        data: np.ndarray,
        final_shape: Union[tuple, list, np.ndarray],
        values: float=0
) -> np.ndarray:
    """Return padded data so it matches the provided final_shape"""

    shape = data.shape

    axis0_pad_width = (final_shape[0] - shape[0]) // 2
    axis1_pad_width = (final_shape[1] - shape[1]) // 2
    axis2_pad_width = (final_shape[2] - shape[2]) // 2

    return np.pad(
        data,
        (
            (axis0_pad_width, axis0_pad_width + (final_shape[0] - shape[0]) % 2),
            (axis1_pad_width, axis1_pad_width + (final_shape[1] - shape[1]) % 2),
            (axis2_pad_width, axis2_pad_width + (final_shape[2] - shape[2]) % 2)
        ),
        mode="constant",
        constant_values=values
    )

def crop_at_center(
        data: np.ndarray,
        final_shape: Union[list, tuple, np.ndarray]
) -> np.ndarray:
    """
    Crop 3D array data to match the final_shape. Center of the input
    data remains the center of cropped data.
    :param data: 3D array data to be cropped (np.array).
    :param final_shape: the targetted shape (list). If None, nothing
    happens.
    :returns: cropped 3D array (np.array).
    """
    shape = data.shape
    final_shape = np.array(final_shape)

    if not (final_shape <= data.shape).all():
        print(
            "One of the axis of the final shape is larger than "
            f"the initial axis (initial shape: {shape}, final shape: "
            f"{tuple(final_shape)}).\nDid not proceed to cropping."
        )
        return data

    c = np.array(shape) // 2  # coordinates of the center
    to_crop = final_shape // 2  # indices to crop at both sides
    # if final_shape[i] is odd, center[i] must be at
    # final_shape[i] + 1 // 2
    plus_one = np.where((final_shape % 2 == 0), 0, 1)

    cropped = data[
        c[0] - to_crop[0]: c[0] + to_crop[0] + plus_one[0],
        c[1] - to_crop[1]: c[1] + to_crop[1] + plus_one[1],
        c[2] - to_crop[2]: c[2] + to_crop[2] + plus_one[2]
    ]

    return cropped


def compute_distance_from_com(
        data: np.ndarray,
        com: Union[tuple, list, np.ndarray]=None
) -> np.ndarray:
    """
    Return a np.ndarray of the same shape of the provided data.
    (i, j, k) Value will correspond to the distance of the (i, j, k)
    voxel in data to the center of mass if that voxel is not null.
    """
    nonzero_coordinates = np.nonzero(data)
    distance_matrix = np.zeros(shape=data.shape)

    if com is None:
        com = center_of_mass(data)

    for x, y, z in zip(nonzero_coordinates[0],
                       nonzero_coordinates[1],
                       nonzero_coordinates[2]):
        distance = np.sqrt((x-com[0])**2 + (y-com[1])**2 + (z-com[2])**2)
        distance_matrix[x, y, z] = distance

    return distance_matrix


def zero_to_nan(
        data: np.ndarray,
        boolean_values: bool=False
) -> np.ndarray:
    """Convert zero values to np.nan."""
    return np.where(data == 0, np.nan, 1 if boolean_values else data)


def nan_to_zero(
        data: np.ndarray,
        boolean_values: bool=False
) -> np.ndarray:
    """Convert np.nan values to 0."""
    return np.where(np.isnan(data), 0, 1 if boolean_values else data)


def to_bool(data: np.ndarray, nan_value: bool=False) -> np.ndarray:
    """Convert values to 1 (True) if not nan otherwise to 0 (False)"""
    return np.where(np.isnan(data), np.nan if nan_value else 0, 1)


def nan_center_of_mass(
        data: np.ndarray,
        return_int: bool=False
) -> np.ndarray:
    """
    Compute the center of mass of a np.ndarray that may contain
    nan values.
    """
    if not np.isnan(data).any():
        com = center_of_mass(data)

    non_nan_coord = np.where(np.invert(np.isnan(data)))
    com = np.average(
        [non_nan_coord], axis=2,
        weights=data[non_nan_coord]
    )[0]
    if return_int:
        return tuple([int(round(e)) for e in com])
    return tuple(com)


class PeakCenteringHandler:
    """
    A class to handle centering of Bragg peak.
    """

    @staticmethod
    def get_masked_data(
            data: np.ndarray,
            where: tuple,
            crop: List[list]
    ) -> None:
        """
        Return the masked data. Data are masked outside of the box
        defined by the crop and where parameter.
        """

        mask = np.ones_like(data)
        shape = data.shape

        slices = [np.s_[:] for k in range(len(shape))]
        for i, s in enumerate(shape):
            slices[i] = np.s_[
                np.max([where[i]-crop[i][0], 0]):
                np.min([where[i]+crop[i][1], s])
            ]
        slices = tuple(slices)
        mask[slices] = 0

        return np.ma.array(data, mask=mask)

    @staticmethod
    def get_position(method: Union[str, list], data: np.ndarray) -> tuple:
        """
        Get the position in the full data frame given the provided
        method.
        """

        if isinstance(method, str):
            if method == "max":
                return find_max_pos(data)
            if method == "com":
                return nan_center_of_mass(data, return_int=True)

        elif isinstance(method, (tuple, list)):
            if all(isinstance(e, int) for e in method):
                return method

        raise ValueError(
            f"'method' cannot be {method} (type {type(method)})\n"
            "It must be either 'max', 'com' or a list or a tuple of int."
        )

    @classmethod
    def chain_centering(
            cls,
            data: np.ndarray,
            output_shape: Union[list ,tuple, np.ndarray],
            methods: List[Union[str, tuple]]
    ) -> Tuple[np.ndarray, tuple]:
        """
        Main method of the class. It runs several centering methods,
        defined in the methods parameter. Each time, a mask is created
        and the next method takes into account the new mask.

        Note that the cropping of the data is done according to the
        following convention:
        position of the reference
        (com or max...) must always be at
        cropped_data[output_shape[i]//2].
            - if output_shape[i] is even: the exact center does not
            exist and the center will be shift towards the higher value
            indexes. More values before the center than after.
            - if output_shape[i] is odd, exact center can be defined and
            the numbers of values before and after the center are equal.
        """

        output_shape = np.array(output_shape)

        # define how much to crop data
        # plus_one is whether or not to add one to the bounds.
        plus_one = np.where((output_shape % 2 == 0), 0, 1)
        crop = [
            [output_shape[i]//2, output_shape[i]//2 + plus_one[i]]
            for i in range(len(output_shape))
        ]

        # For the first method, the data are not masked.
        masked_data = data

        for method in methods:
            print(f"Centering with method: {method}... ", end="")
            # position is found in the masked data
            position = cls.get_position(method, masked_data)
            # mask the data in the roi defined by the output shape and
            # position
            masked_data = cls.get_masked_data(
                data,
                where=position,
                crop=crop
            )
            print(masked_data)

        # select the data that are not masked
        indexes_of_interest = np.where(np.logical_not(masked_data.mask))
        slices = [np.s_[:] for k in range(len(data.shape))]
        for i in range(len(data.shape)):
            bounds = (
                np.min(indexes_of_interest[i]),
                np.max(indexes_of_interest[i]) + 1
            )
            slices[i] = np.s_[bounds[0]:bounds[1]]

        return masked_data.data[tuple(slices)], position


def compute_corrected_angles(
        inplane_angle: float,
        outofplane_angle: float,
        detector_coordinates: tuple,
        detector_distance: float,
        direct_beam_position: tuple,
        pixel_size: float=55e-6,
        verbose=False
) -> tuple[float, float]:
    """
    Compute the detector corrected angles given the angles saved in the
    experiment data file and the position of interest in the detector frame

    :param inplane_angle: in-plane detector angle in degrees (float).
    :param outofplane_angle out-of-plane detector angle in degrees
    (float).
    :param detector_coordinates: the detector coordinates of the point
    of interest (tuple or list).
    :param detector_distance: the sample to detector distance
    :param direct_beam_position: the direct beam position in the
    detector frame (tuple or list).
    :param pixel_size: the pixel size (float).
    :param verbose: whether or not to print the corrections (bool).

    :return: the two corrected angles.
    """
    inplane_correction = np.rad2deg(
        np.arctan(
            (detector_coordinates[1] - direct_beam_position[0])
            * pixel_size
            / detector_distance
        )
    )

    outofplane_correction = np.rad2deg(
        np.arctan(
            (detector_coordinates[0] - direct_beam_position[1])
            * pixel_size
            / detector_distance
        )
    )

    corrected_inplane_angle = float(inplane_angle - inplane_correction)
    corrected_outofplane_angle = float(outofplane_angle - outofplane_correction)

    if verbose:
        print(
            f"current in-plane angle: {inplane_correction}\n"
            f"in-plane angle correction: {corrected_inplane_angle}\n"
            f"corrected in-plane angle: {corrected_inplane_angle}\n\n"
            f"current out-of-plane angle: {outofplane_angle}\n"
            f"out-of-plane angle correction: {outofplane_correction}\n"
            f"corrected out-of-plane angle: {corrected_outofplane_angle}"
        )
    return corrected_inplane_angle, corrected_outofplane_angle


def find_suitable_array_shape(
        support: np.array,
        padding: Optional[list]=None,
        symmetrical_shape: Optional[bool]=True
) -> np.array:
    """Find a more suitable shape of an array"""
    if padding is None:
        padding = [4, 4, 4]
    hull = find_hull(support, boolean_values=True)
    coordinates = np.where(hull == 1)
    axis_0_range = np.ptp(coordinates[0]) + padding[0]
    axis_1_range = np.ptp(coordinates[1]) + padding[1]
    axis_2_range = np.ptp(coordinates[2]) + padding[2]

    if symmetrical_shape:
        return np.repeat(
            np.max(np.array([axis_0_range, axis_1_range, axis_2_range])),
            3
        )

    return np.array([axis_0_range, axis_1_range, axis_2_range])


def find_isosurface(
        amplitude: np.ndarray,
        nbins: Optional[int]=100,
        sigma_criterion: Optional[float]=3,
        plot: Optional[bool]=False,
        show: Optional[bool]=False
) -> Union[Tuple[float, matplotlib.axes.Axes], float]:
    """
    Estimate the isosurface from the amplitude distribution

    :param amplitude: the 3D amplitude volume (np.array)
    :param nbins: the number of bins to considerate when making the
    histogram (Optional, int)
    :param sigma_criterion: the factor to compute the isosurface wich is
    calculated as: mu - sigma_criterion * sigma. By default set to 3.
    (Optional, float)
    :param show: whether or not to show the the figure

    :return: the isosurface value and the figure in which the histogram
    was plotted
    """

    # normalize and flatten the amplitude
    flattened_amplitude = normalize(amplitude).ravel()

    counts, bins = np.histogram(flattened_amplitude, bins=nbins)

    # remove the background
    background_value = bins[np.where(counts == counts.max())[0]+1+ nbins//20]
    filtered_amplitude = flattened_amplitude[
        flattened_amplitude > background_value
    ]

    # redo the histogram with the filtered amplitude
    counts, bins = np.histogram(filtered_amplitude, bins=nbins, density=True)
    bin_centres = (bins[:-1] + bins[1:]) / 2
    bin_size = bin_centres[1] - bin_centres[0]

    # fit the amplitude distribution
    kernel = gaussian_kde(filtered_amplitude)
    x = np.linspace(0, 1, 1000)
    fitted_counts = kernel(x)

    max_index = np.argmax(fitted_counts)
    right_gaussian_part = np.where(x >= x[max_index], fitted_counts, 0)

    # find the closest indexes
    right_HM_index = np.argmin(
        np.abs(right_gaussian_part - fitted_counts.max() / 2)
    )  
    left_HM_index = max_index - (right_HM_index - max_index)

    fwhm = x[right_HM_index] - x[left_HM_index]
    sigma_estimate = fwhm / 2*np.sqrt(2*np.log(2))
    isosurface = x[max_index] - sigma_criterion * sigma_estimate

    if plot or show:
        fig, ax = matplotlib.pyplot.subplots(1, 1, figsize=(8, 5))
        ax = plot_background(ax)
        ax.bar(
            bin_centres,
            counts,
            width=bin_size,
            color="dodgerblue",
            alpha=0.9,
            edgecolor=(0, 0, 0, 0.25),
            label="amplitude distribution"
        )
        sns.kdeplot(
            filtered_amplitude,
            ax=ax,
            alpha=0.3,
            fill=True,
            color="navy",
            label="density estimate"
        )
        ax.axvspan(
            x[left_HM_index],
            x[right_HM_index],
            edgecolor="k",
            facecolor="green",
            alpha=0.2,
            label="FWHM"
        )
        ax.plot(
            [isosurface, isosurface],
            [0, fitted_counts[(np.abs(x - isosurface)).argmin()]],
            solid_capstyle="round",
            color="lightcoral",
            lw=5,
            label=f"isosurface estimated at {isosurface:0.3f}"
        )

        ax.set_xlabel("normalized amplitude", size=14)
        ax.set_ylabel("counts",  size=14)
        ax.legend()
        fig.suptitle("Reconstructed amplitude distribution", size=16)
        fig.tight_layout()
        if show:
            matplotlib.pyplot.show()
        return isosurface, fig
    return isosurface