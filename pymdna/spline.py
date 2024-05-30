import numpy as np
from scipy.interpolate import splprep, splev
from scipy.integrate import cumtrapz
import matplotlib.pyplot as plt
from .utils import RigidBody 

"""
This script contains the class `SplineFrames` which is used to generate and manipulate a 3D spline path based on 
input control points. This class provides a set of methods to initialize the spline, evaluate the spline at 
multiple points, distribute points along the spline, compute frames (basis vectors) along the path, plot frames, 
and test the correctness of the frames. The control points, spline degree, closed path option, and the up vector 
are all configurable. The implementation of the class is based on the Bishop Frame method.


The Bishop Frame method is a technique used in computer graphics and robotics for generating a smooth frame of reference along a 3D curve or path. 
It's often used in situations where an object must follow a path smoothly, such as camera paths in computer graphics or the path of a robot's arm.

The method generates an orthogonal frame of reference (i.e., a coordinate system consisting of three mutually perpendicular vectors) along the curve. 
This frame of reference is typically made up of:

    A tangent vector (usually denoted as T), which is tangent to the curve and points in the direction of the curve.
    A normal vector (usually denoted as N), which is perpendicular to the tangent vector.
    A binormal vector (usually denoted as B), which is perpendicular to both the tangent and normal vectors.

The Bishop Frame method differs from other methods, such as the Frenet-Serret Frame, in that it does not assume the curve is torsion-free, 
and thus provides a smoother frame along the curve. 

Implementation in the context of the SplineFrames class:
In the _compute_frames method, frames (consisting of a position, right, up, and forward vectors) are computed for each point along the spline. 
The 'forward' vector is essentially the tangent vector (T) at that point, calculated from the derivative of the spline. 
The 'up' vector is derived by removing any component of the up vector (initialized as [0,0,1]) that lies along the forward direction 
(ensuring it's orthogonal to the tangent), and normalizing it. The 'right' vector is calculated as the cross product of the forward and up vectors.
The 'up' vector here, unlike in the Frenet-Serret method, is influenced by a user-specified 'up' direction, 
not just the curvature of the path. This makes the frame less likely to flip or twist sharply when the path changes direction, 
a characteristic feature of the Bishop frame method. The distribute_points method ensures that frames are generated at regular intervals along the curve 
(based on the arc length), which further aids in creating a smooth progression of frames.
Note, in this implementation, the 'forward' vector is synonymous with the tangent, the 'right' vector with the binormal, and the 'up' vector with the normal.


Example usage:
control_points = np.array([[0, 0, 0], [1, 1, 1], [2, -1, 2], [3, 0, 1], [4, 2, 1]])*1.5
d = 0.34

Spline = SplineFrames(
    control_points=control_points, 
    frame_spacing=d,
    degree=3, 
    closed=False
)
Spline.plot_frames()

Background:

The problem in computer graphics to generate coordinate frames along a spline with minimal torsion. 
The traditional method using Frenet Frames is problematic at inflection points where the second derivative is zero, leading to undefined normal and binormal vectors and causing unwanted inversions.
This can partially be metigated by defining a world-up vector, but this still leads to unwanted twisting at inflection points and other points where the curve is not smooth.
The solution proposed involves using an initial coordinate frame at the beginning of the curve and propagating it along the spline incrementally, avoiding dependence on an up-axis. 
This technique avoids issues at inflection points and with curves that could induce torsion, by computing the next frame based on the previous frame and the first derivative of the curve.

Given the previous coordinate frame T, N, B, one can compute the next coordinate frame T' N' and B' as follows:

   - Compute T' analytically, by evaluating the first derivative of the curve
   - Compute the axis of rotation from T to T' by taking the cross product of T and T', and then normalizing
   - Compute the angle of rotation by computing the angle between T and T'
   - Rotate N using the axis and angle computed above to find N'
   - Compute the cross product of T' and N' to find B'

I think I used another way to mitigate this problem by updating the world vector... 

Refs:
- Calculation of Reference Frames along a Space Curve (51K) in Graphics Gems, Academic Press, 1990 in Graphics Gems, Academic Press, 1990 in Graphics Gems, Academic Press, 1990
- Computing Coordinate Frames on a Spline with Minimal Torsion, James Bird, https://jbrd.github.io/2011/06/19/computing-coordinate-frames-on-a-spline-with-minimal-torsion.html
- Two moving coordinate frames for sweeping along a 3D trajectory, Computer Aided Geometric Design 3 (1986) 217-229 217 North-Holland

"""

class SplineFrames:
    
    def __init__(self, control_points, degree=3, closed=False, up_vector=[0, 0, 1],frame_spacing=0.34, twist=True, bp_per_turn=10.5, frame_tolerance=0.5, verbose=False, num_points=1000, initial_frame=None, modified_ranges=[]):
        """
        Initializes the SplineFrames class.

        Args:
            control_points (numpy.ndarray): Control points defining the path.
            degree (int, optional): Degree of the spline. Defaults to 3.
            closed (bool, optional): Indicates if the path is closed. Defaults to False.
            up_vector (list or numpy.ndarray, optional): Up vector for frame computation. Defaults to [0, 0, 1].
        """
        self.control_points = control_points
        self.n = num_points
        self.degree = degree
        self.closed = closed
        self.up_vector = np.array(up_vector)
        self.frame_spacing = frame_spacing
        self.bp_per_turn = bp_per_turn
        self.frame_tolerance = frame_tolerance
        self.initial_frame = initial_frame  # Added variable for the initial frame if we need to align the first frame with a given frame
        self.tck = None
        self.curve = None
        self.der1 = None
        self.der2 = None
        self.arc_length = None
        self.point_indices = None
        self.frames = []
        self.verbose = verbose
        self._initialize_spline()
        self._evaluate_spline()
        self.distribute_points()
        self.test_frames()
        if twist:
            self.twist_frames(modified_ranges=modified_ranges)

    def update_initial_frame(self, initial_frame):
        """
        Updates the initial frame.

        Args:
            initial_frame (tuple): Tuple containing the position, right, up, and forward vectors of the frame.

        Returns:
            self: Returns the instance of the class.
        """
        self.initial_frame = initial_frame
        self._compute_frames()
        return self

    def update_control_points(self, control_points):
        """
        Updates the control points defining the path.

        Args:
            control_points (numpy.ndarray): Control points defining the path.

        Returns:
            self: Returns the instance of the class.
        """
        self.control_points = control_points
        self._initialize_spline()
        self._evaluate_spline()
        return self

    def update_spline_degree(self, degree):
        """
        Updates the degree of the spline.

        Args:
            degree (int): Degree of the spline.

        Returns:
            self: Returns the instance of the class.
        """
        self.degree = degree
        self._initialize_spline()
        self._evaluate_spline()
        return self

    def update_closed(self, closed):
        """
        Updates the closed property indicating if the path is closed.

        Args:
            closed (bool): Indicates if the path is closed.

        Returns:
            self: Returns the instance of the class.
        """
        self.closed = closed
        self._initialize_spline()
        self._evaluate_spline()
        return self

    def update_up_vector(self, up_vector):
        """
        Updates the up vector used for frame computation. Not used at the moment

        Args:
            up_vector (list or numpy.ndarray): Up vector for frame computation.

        Returns:
            self: Returns the instance of the class.
        """
        self.up_vector = np.array(up_vector)
        self._compute_frames()
        return self

    def _initialize_spline(self):
        """
        Initializes the spline with the control points.

        Returns:
            self: Returns the instance of the class.
        """
        if self.verbose:
            print("Initializing spline")
        control_points = self.control_points
        # if self.closed:
        #     control_points = np.vstack((self.control_points, self.control_points[0]))

        #     # Calculate tangent vectors at the first and last control points
        #     t_first = self.control_points[1] - self.control_points[0]
        #     t_last = self.control_points[-1] - self.control_points[-2]

        #     # Adjust the control points to ensure consistent tangent directions
        #     if np.dot(t_first, t_last) < 0:
        #         control_points[-1] = control_points[-1] * -1

        tck, _ = splprep(control_points.T, s=0, k=self.degree)#, per=self.closed)
        self.tck = tck
        return self

    def _evaluate_spline(self):
        """
        Evaluates the spline curve and its derivatives.

        Args:
            n (int, optional): Number of points to sample on the spline. Defaults to 1000.

        Returns:
            self: Returns the instance of the class.
        """
        if self.verbose:
            print("Evaluating spline")
        dt = 1 / self.n
        self.v = np.arange(0, 1 + dt, dt)
        self.curve = np.array(splev(self.v, self.tck)).T
        self.der1 = np.array(splev(self.v, self.tck, der=1)).T
        #self.der2 = np.array(splev(self.v, self.tck, der=2)).T

        if self.verbose:
            print("Calculating arc length")
        # Calculate the arc length of the spline
        arc_diffs = np.diff(self.curve, axis=0)
        
        arc = np.sqrt((arc_diffs**2).sum(axis=1))
        self.arc_length = np.hstack([0, cumtrapz(arc)])
        return self

    def distribute_points(self):
        """
        D,
        and evaluate the derivatives at these points. Adjusts the spacing to match the first and last points of the spline.

        Args:
            d (float): Desired distance between points.
            derivative_order (int): The order of the derivative to compute.

        Returns:
            equidistant_points: Equidistant points along the spline.
            derivatives: Derivatives at the equidistant points.
        """

        # Calculate the new segment length within the specified tolerance
        adjusted_arc_length = self.arc_length[-1] - self.frame_spacing  # Subtract the first and last segments
        num_segments = np.round(adjusted_arc_length / self.frame_spacing)
        new_segment_length = adjusted_arc_length / num_segments
        
        # If the new segment length is within the tolerance, proceed with the distribution
        if abs(new_segment_length - self.frame_spacing) <= self.frame_tolerance:
            self.segment_lengths = np.linspace(new_segment_length, adjusted_arc_length, int(num_segments))

            # Including the first and last points (and not the last segment if closed topology)
            self.t_values = [0] + list(np.interp(self.segment_lengths, self.arc_length, self.v[:len(self.arc_length)]))
            if not self.closed:
                self.t_values += [1] 
    
            if self.verbose:
                print(f"Evenly distributing {len(self.t_values)} points along the spline and computing derivatives.")

            # Evaluate the spline and its derivatives at the reparametrized t values
            equidistant_points = np.array(splev(self.t_values, self.tck)).T
            # Use difference vectors of equidistant points to calculate the derivatives
            derivatives = np.diff(equidistant_points, axis=0)
            #print(derivatives.shape,equidistant_points.shape)
            # Add the last derivative to the end
            derivatives = np.vstack([derivatives, derivatives[-1]])
            # Last point some numerical error that inverts the direction of the last point? Need to do more testing...
            #derivatives = np.array(splev(self.t_values, self.tck, der=1)).T
        else:
            raise ValueError(f"Cannot find a suitable segment length within the tolerance of {self.frame_tolerance} nm rise.")

        # Store or return the results
        self.positions = equidistant_points
        self.derivatives = derivatives
        # Assuming self._compute_frames() updates self with the new frames
        self._compute_frames()
        return self

    def rotation_matrix_from_vectors(self,vec1, vec2):
        """ Find the rotation matrix that aligns vec1 to vec2 """
        a, b = (vec1 / np.linalg.norm(vec1)).reshape(3), (vec2 / np.linalg.norm(vec2)).reshape(3)
        v = np.cross(a, b)
        c = np.dot(a, b)
        s = np.linalg.norm(v)
        kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        rotation_matrix = np.eye(3) + kmat + kmat.dot(kmat) * ((1 - c) / (s ** 2))
        return rotation_matrix


    def _compute_initial_frame(self):
        # Compute the initial frame based on the first derivative and up_vector
        T = self.derivatives[0] / np.linalg.norm(self.derivatives[0])
        N = np.cross(T, self.up_vector)
        if np.linalg.norm(N) < 1e-6: # Fallback if T and up_vector are parallel
            N = np.cross(T, np.array([1, 0, 0]) if abs(T[2]) < 0.9 else np.array([0, 1, 0]))
        N = N / np.linalg.norm(N)
        B = np.cross(T,N)
        #print('det initial frame',np.linalg.det(np.array([T,N,B])))
        self.frames.append((self.positions[0], N, B, T))
        #self.frames.append((self.positions[0], T, N, B))
   

    def _slide_frames_(self):
        # Iterate through each position along the curve, starting from the second position
        for i in range(1, len(self.positions)):
            # Get the last tangent vector (T) from the previously computed frames
            T_prev = self.frames[-1][1]  
            # Compute the new tangent vector (T') analytically as the normalized first derivative of the curve at the current position
            T = self.derivatives[i] / np.linalg.norm(self.derivatives[i])
            
            # Compute the axis of rotation as the normalized cross product of T and T', indicating the direction to rotate N to N'
            axis = np.cross(T_prev, T)
            # Check if the axis is significant to avoid division by zero and unnecessary rotation calculations
            if np.linalg.norm(axis) > 1e-6:
                axis = axis / np.linalg.norm(axis)  # Normalize the axis to ensure it has unit length
                # Compute the angle of rotation by the arccos of the dot product of T and T', clipped to [-1, 1] to avoid numerical issues
                angle = np.arccos(np.clip(np.dot(T_prev, T), -1.0, 1.0))
                # Rotate the normal vector (N) using the computed axis and angle to find the new normal vector (N')
                N = RigidBody.rotate_vector(self.frames[-1][2], axis, angle)
            else:
                # If the axis of rotation is negligible, use the previous normal vector (N) without rotation
                N = self.frames[-1][2]
                
            # Compute the binormal vector (B') as the cross product of T' and N', completing the coordinate frame
            B = np.cross(T, N)
            # Append the new coordinate frame (position, T', N', B') to the frames list for later use
            #print('det slide:',i,np.linalg.det(np.array([T,N,B])))
            self.frames.append((self.positions[i], T, N, B)) # original
            #self.frames.append((self.positions[i], N, B, T)) # original
    
    def _slide_frames(self):
        # Iterate through each position along the curve, starting from the second position
        for i in range(1, len(self.positions)):
            # Get the last tangent vector (T) from the previously computed frames
            T_prev = self.frames[-1][3]  
            # Compute the new tangent vector (T') analytically as the normalized first derivative of the curve at the current position
            T = self.derivatives[i] / np.linalg.norm(self.derivatives[i])
            
            # Compute the axis of rotation as the normalized cross product of T and T', indicating the direction to rotate N to N'
            axis = np.cross(T_prev, T)
            # Check if the axis is significant to avoid division by zero and unnecessary rotation calculations
            if np.linalg.norm(axis) > 1e-6:
                axis = axis / np.linalg.norm(axis)  # Normalize the axis to ensure it has unit length
                # Compute the angle of rotation by the arccos of the dot product of T and T', clipped to [-1, 1] to avoid numerical issues
                angle = np.arccos(np.clip(np.dot(T_prev, T), -1.0, 1.0))
                # Rotate the normal vector (N) using the computed axis and angle to find the new normal vector (N')
                N = RigidBody.rotate_vector(self.frames[-1][1], axis, angle)
            else:
                # If the axis of rotation is negligible, use the previous normal vector (N) without rotation
                N = self.frames[-1][1]
                
            # Compute the binormal vector (B') as the cross product of T' and N', completing the coordinate frame
            B = np.cross(T, N)
            # Append the new coordinate frame (position, T', N', B') to the frames list for later use
            # print('det slide:',i,np.linalg.det(np.array([T,N,B])))
            self.frames.append((self.positions[i], N, B, T)) # original


    def _compute_frames(self):
        """
        Computes the coordinate frames on a spline with minimal torsion.
        Source: https://jbrd.github.io/2011/06/19/computing-coordinate-frames-on-a-spline-with-minimal-torsion.html

        """
        if self.initial_frame is not None:
            # Directly use the provided custom initial frame
            self.frames.append((self.positions[0], *self.initial_frame[1:]))
        else:
            # Compute the initial frame based on the first derivative and up_vector
            self._compute_initial_frame()
        
        # Compute frames for the rest of the points along the path
        self._slide_frames()
        
        # Convert the list of frames to a NumPy array for efficient storage and manipulation
        self.frames = np.array(self.frames)
        # # Swap the T and B vectors to match the expected order for the DNA generation
        # self.frames[:, [1, 3]] = self.frames[:, [3, 1]] 

    def _compute_frames_old(self):
        """
        Computes the frames along the spline.

        Returns:
            self: Returns the instance of the class.
        """
        self.frames = []

        # Compute frames for the rest of the points
        for derivative,position in zip(self.derivatives, self.positions):
            forward = derivative / np.linalg.norm(derivative)
            up = self.up_vector - forward * np.dot(forward, self.up_vector)
            if np.linalg.norm(up) < 1e-6:
                if abs(forward[2]) < 0.9:
                    up = np.array([0, 0, 1])
                else:
                    up = np.array([1, 0, 0])

            up = up / np.linalg.norm(up)
            right = np.cross(forward, up)
            self.frames.append((position, right, up, forward))


        if self.initial_frame is not None:

            # If an initial frame is provided, use it to transform the frames 
            # to align the first fram with the initial frame and then transform the rest of the frames accordingly
            # use the tangent up vector as the direction in which the initial frame is aligned
            initial_position, _, _, initial_forward = self.initial_frame

            # Compute rotation matrix to align the first frame's forward vector with the initial frame's forward vector
            first_frame_position, _, _, first_frame_forward = self.frames[0]
            rot_matrix = self.rotation_matrix_from_vectors(first_frame_forward, initial_forward)

            # Compute translation
            translation = initial_position - first_frame_position

            # Apply rotation and translation to all frames
            transformed_frames = [
                (np.dot(rot_matrix, position) + translation,
                 np.dot(rot_matrix, right),
                 np.dot(rot_matrix, up),
                 np.dot(rot_matrix, forward))
                for position, right, up, forward in self.frames]

            # Be carful only the frames are now updated, not the control points, positions, derivatives, etc.
            self.frames = np.array(transformed_frames)

        self.frames = np.array(self.frames)
        return self

    def plot_frames(self, fig=False, equal_bounds=False, equal=True, spline=False,control_points=False):
        """
        Plots the frames along the spline.

        Note: This method needs to be called after the frames are computed.

        Returns:
            None
        """
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        for frame in self.frames:
            position, right, up, forward = frame
            ax.quiver(*position, *right, length=0.2, color='g')
            ax.quiver(*position, *up, length=0.2, color='b')
            ax.quiver(*position, *forward, length=0.2, color='r')
        
        _ = self.tck[0]  # Spline parameters for plotting
        u = np.linspace(0, 1, 100)
        spline_points = np.array(splev(u, self.tck)).T
        if spline:
            ax.plot(*spline_points.T, color='gray', label='Spline')
        if equal_bounds:
            # Compute bounds
            all_points = np.vstack([spline_points, *[frame[0] for frame in self.frames]])
            max_bound = np.max(np.abs(all_points))
            
            ax.set_xlim([-max_bound, max_bound])
            ax.set_ylim([-max_bound, max_bound])
            ax.set_zlim([-max_bound, max_bound])
        if control_points:
            ax.scatter(*self.control_points.T, color='black', label='Control Points')
        if equal:
            ax.axis('equal')

        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')

        if spline or control_points:
            ax.legend()
  
        if fig:
            return fig, ax 
        else:
            return None 

    def test_frames(self):
        """
        Tests the computed frames for correctness.

        Args:
            frames (list): List of frames to test.

        Returns:
            None
        """
        for i in range(len(self.frames)-1):
            frame1 = self.frames[i]
            frame2 = self.frames[i+1]

            right1, up1 = frame1[1:3]
            right2, up2 = frame2[1:3]

            # Check if right vectors have flipped
            right_dot_product = np.dot(right1, right2)
            if right_dot_product < 0:
                angle_deviation = np.degrees(np.arccos(np.clip(np.dot(right1, right2), -1.0, 1.0)))
                print(f"Warning: Right Vectors may have flipped. Frame {i+1} to Frame {i+2}. Angle Deviation: {angle_deviation:.2f} degrees")

            # Check if up vectors have flipped
            up_dot_product = np.dot(up1, up2)
            if up_dot_product < 0:
                angle_deviation = np.degrees(np.arccos(np.clip(np.dot(up1, up2), -1.0, 1.0)))
                print(f"Warning: Up Vectors may have flipped. Frame {i+1} to Frame {i+2}. Angle Deviation: {angle_deviation:.2f} degrees")

        return None
    
    def twist_frames(self, modified_ranges=[], plot=False):
        self.twister = Twister(frames=self.frames, bp_per_turn=self.bp_per_turn, modified_ranges=modified_ranges, plot=plot, circular=self.closed)
        # This can be a separate call if you don't want to twist immediately upon calling twist_frames
        self.twister.compute_and_plot_twists()
        if self.closed:
            adj = self.twister.adjustment_factor
            print(f"Structure is requested to be circular:\n Excess twist per base to make ends meet: {adj-(360/self.bp_per_turn):.2f} degrees")

        
class Twister:
    
    def __init__(self, frames, bp_per_turn=10.5, modified_ranges=[], circular=False, plot=False):
        """
        Initialize the TwistFrames class.

        If circular DNA, adjust the twist angles to ensure the total twist is a multiple of 360
        Currently this is done by slightly increasing the twist angle for each base pair
        The adjustment factor is stored in self.adjustment_factor

        Args:
            spline: The spline object with frames to be twisted.
            bp_per_turn (float, optional): Number of base pairs per turn. Default is 10.5.
            modified_ranges (list, optional): List of tuples containing the start and end indices 
                                              of the modified ranges and the twist angle.
            plot (bool, optional): Whether to plot the twist data.
        """
        self.circular = circular
        self.frames = frames
        self.bp_per_turn = bp_per_turn
        self.modified_ranges = modified_ranges
        self.plot = plot
        self.twists = []
        self.accumulated_twists = []
   
    def calculate_twist_angle(self, bp_index, standard_twist_angle_degrees):
        """
        Calculate the twist angle for a given base pair index.
        
        Args:
            bp_index (int): The base pair index.
            standard_twist_angle_degrees (float): Standard B-DNA twist angle in degrees.
            
        Returns:
            float: The twist angle for the given base pair index.
        """
        for start, end, twist in self.modified_ranges:
            if start <= bp_index < end:
                return twist
        return standard_twist_angle_degrees

    def rotate_basis(self, frame, twist_angle_degrees):
        """
        Rotate the basis vectors.
        
        Args:
            frame (np.ndarray): DNA frame of shape (1, 4, 3).
            twist_angle_degrees (float): The angle to twist in degrees.
            
        Returns:
            tuple: Rotated basis vectors.
        """
        N, B, T = frame[0], frame[1], frame[2] 
        twist_angle_radians = np.deg2rad(twist_angle_degrees)
        # twist_angle_radians = 0
        #print(N,B, twist_angle_degrees)
        #print('pre twist det:',np.linalg.det(np.array([N,B,T])))
        # R = RigidBody.euler2rotmat(T*twist_angle_degrees)
        # B_rotated = np.dot(R,B)
        # N_rotated = np.dot(R,N)

        B_rotated = RigidBody.rotate_vector(B, T, twist_angle_radians)
        N_rotated = RigidBody.rotate_vector(N, T, twist_angle_radians)
        #print(N_rotated,B_rotated)
        # Directly modify the input frame
        frame[0] = N_rotated 
        frame[1] = B_rotated
        #print('twist det:',np.linalg.det(np.array([N_rotated,B_rotated,T])))
        return frame

    def plot_twist_data(self, twists, accumulated_twists):
        """
        Plot the twist data.
        
        Args:
            twists (list): List of twist angles.
            accumulated_twists (list): List of accumulated twist angles.
        """
        _, ax = plt.subplots(1, 2, figsize=(6, 3))
        _.tight_layout()
        ax[0].plot(np.array(twists))
        ax[0].set_xlabel('Base pair steps')
        ax[0].set_ylabel('Twist angle (degrees)')
        ax[1].plot(np.array(accumulated_twists))
        ax[1].set_xlabel('Base pair steps')
        ax[1].set_ylabel('Accumulated twist angle (degrees)')

    def compute_and_plot_twists(self):
        """
        Compute twists for the DNA frames based on the given twist angle and optionally plot the data.
        """
        n_bp = self.frames.shape[0]
        standard_twist_angle_degrees = 360 / self.bp_per_turn
        total_twist = sum(self.calculate_twist_angle(bp, standard_twist_angle_degrees) for bp in range(n_bp))

        # Adjust the twist angles for circular DNA
        if self.circular:
            # If circular DNA, adjust the twist angles to ensure the total twist is a multiple of 360
            # Currently this is done by slightly increasing the twist angle for each base pair
            total_twist = ((total_twist // 360) + 1) * 360
            adjustment_factor = total_twist / n_bp
            self.adjustment_factor = adjustment_factor
        else:
            adjustment_factor = standard_twist_angle_degrees

        for bp_idx in range(n_bp):
            twist_angle_degrees = self.calculate_twist_angle(bp_idx, adjustment_factor)
            accumulated_twist = sum(self.calculate_twist_angle(bp, adjustment_factor) for bp in range(bp_idx))
            
            # Adjusting only the basis vectors (indexing from 1 onwards)
            self.frames[bp_idx, 1:] = self.rotate_basis(self.frames[bp_idx, 1:], accumulated_twist)
            
            self.twists.append(twist_angle_degrees)
            self.accumulated_twists.append(accumulated_twist)

        if self.plot:
            self.plot_twist_data(self.twists, self.accumulated_twists)