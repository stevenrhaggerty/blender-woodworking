import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.geometry import distance_point_to_plane
from math import pi
from woodwork.tenon_mortise_builder import (TenonMortiseBuilder,
                                            FaceToBeTransformed,
                                            nearly_equal)


# is_face_planar
#
# Tests a face to see if it is planar.
def is_face_planar(face, error=0.0005):
    for v in face.verts:
        d = distance_point_to_plane(v.co, face.verts[0].co, face.normal)
        if d < -error or d > error:
            return False
    return True


def is_face_rectangular(face, error=0.0005):
    for loop in face.loops:
        perp_angle = loop.calc_angle() - (pi / 2)
        if perp_angle < -error or perp_angle > error:
            return False
    return True


class TenonOperator(bpy.types.Operator):
    bl_description = "Creates a tenon given a face"
    bl_idname = "mesh.tenon"
    bl_label = "Tenon"
    bl_options = {'REGISTER', 'UNDO'}

    #
    # Class variables
    #

    shortest_length = -1.0
    longest_length = -1.0

    expand_thickness_properties = bpy.props.BoolProperty(name="Expand",
                                                         default=True)
    expand_height_properties = bpy.props.BoolProperty(name="Expand",
                                                      default=True)

    def __check_face(self, face):
        # If we don't find a selected face, we have problem.  Exit:
        if face is None:
            self.report({'ERROR_INVALID_INPUT'},
                        "You must select a face for the tenon.")
            return False

        # Warn the user if face is not 4 vertices.
        if len(face.verts) > 4:
            self.report({'ERROR_INVALID_INPUT'},
                        "Selected face is not quad.")
            return False

        if not is_face_planar(face):
            self.report({'ERROR_INVALID_INPUT'},
                        "Selected face is not planar.")
            return False

        if not is_face_rectangular(face):
            self.report({'ERROR_INVALID_INPUT'},
                        "Selected face is not rectangular.")
            return False
        return True

    @staticmethod
    def __draw_percentage(layout, data, percentage_property, value_property):
        split = layout.split()

        col = split.column()
        col.prop(data, percentage_property, text="", slider=True)

        col = split.column()
        col.enabled = False
        col.prop(data, value_property, text="")

    @staticmethod
    def __draw_thickness_properties(layout, thickness_properties):
        width_side_box = layout.box()
        width_side_box.label(text="Thickness type")
        width_side_box.prop(thickness_properties, "type", text="")
        if thickness_properties.type == "value":
            width_side_box.prop(thickness_properties, "value", text="")
        elif thickness_properties.type == "percentage":
            TenonOperator.__draw_percentage(width_side_box,
                                            thickness_properties,
                                            "percentage", "value")
        width_side_box.label(text="Position")
        width_side_box.prop(thickness_properties, "centered")
        if not thickness_properties.centered:
            width_side_box.label(text="Thickness shoulder type")
            width_side_box.prop(thickness_properties, "shoulder_type",
                                text="")
            if thickness_properties.shoulder_type == "value":
                width_side_box.prop(thickness_properties, "shoulder_value",
                                    text="")
            elif thickness_properties.shoulder_type == "percentage":
                TenonOperator.__draw_percentage(width_side_box,
                                                thickness_properties,
                                                "shoulder_percentage",
                                                "shoulder_value")
            width_side_box.prop(thickness_properties, "reverse_shoulder")

    @staticmethod
    def __draw_haunch_properties(layout, haunch_properties):
        layout.label(text="Haunch depth type")
        layout.prop(haunch_properties, "type",
                    text="")
        if haunch_properties.type == "value":
            layout.prop(haunch_properties,
                        "depth_value", text="")
        elif haunch_properties.type == "percentage":
            TenonOperator.__draw_percentage(layout, haunch_properties,
                                            "depth_percentage", "depth_value")

        layout.label(text="Haunch angle")
        layout.prop(haunch_properties, "angle", text="")

    @staticmethod
    def __draw_height_properties(layout, height_properties):
        length_side_box = layout.box()
        length_side_box.label(text="Height type")
        length_side_box.prop(height_properties, "type", text="")
        if height_properties.type == "value":
            length_side_box.prop(height_properties, "value", text="")
        elif height_properties.type == "percentage":
            TenonOperator.__draw_percentage(length_side_box, height_properties,
                                            "percentage", "value")

        length_side_box.label(text="Position")
        length_side_box.prop(height_properties, "centered")
        if not height_properties.centered:
            length_side_box.label(text="Height shoulder type")
            length_side_box.prop(height_properties, "shoulder_type",
                                 text="")
            if height_properties.shoulder_type == "value":
                length_side_box.prop(height_properties, "shoulder_value",
                                     text="")
            elif height_properties.shoulder_type == "percentage":
                TenonOperator.__draw_percentage(length_side_box,
                                                height_properties,
                                                "shoulder_percentage",
                                                "shoulder_value")

            length_side_box.prop(height_properties, "reverse_shoulder")
            length_side_box.prop(height_properties, "haunched_first_side")
            if height_properties.haunched_first_side:
                haunch_properties = height_properties.haunch_first_side
                TenonOperator.__draw_haunch_properties(length_side_box,
                                                       haunch_properties)
            length_side_box.prop(height_properties, "haunched_second_side")
            if height_properties.haunched_second_side:
                haunch_properties = height_properties.haunch_second_side
                TenonOperator.__draw_haunch_properties(length_side_box,
                                                       haunch_properties)

    # Custom layout
    def draw(self, context):
        layout = self.layout

        tenon_properties = context.scene.tenonProperties
        thickness_properties = tenon_properties.thickness_properties
        height_properties = tenon_properties.height_properties

        row = layout.row(align=True)
        row.alignment = 'EXPAND'
        if not self.expand_thickness_properties:
            row.prop(self, "expand_thickness_properties", icon="TRIA_RIGHT",
                     icon_only=True, text="Width side",
                     emboss=False)
        else:
            row.prop(self, "expand_thickness_properties", icon="TRIA_DOWN",
                     icon_only=True, text="Width side",
                     emboss=False)
            TenonOperator.__draw_thickness_properties(layout,
                                                      thickness_properties)

        row = layout.row(align=True)
        row.alignment = 'EXPAND'
        if not self.expand_height_properties:
            row.prop(self, "expand_height_properties", icon="TRIA_RIGHT",
                     icon_only=True, text="Length side",
                     emboss=False)
        else:
            row.prop(self, "expand_height_properties", icon="TRIA_DOWN",
                     icon_only=True, text="Length side",
                     emboss=False)
            TenonOperator.__draw_height_properties(layout, height_properties)

        layout.label(text="Depth")
        layout.prop(tenon_properties, "depth_value", text="")

    # used to check if the operator can run
    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        tenon_properties = context.scene.tenonProperties
        thickness_properties = tenon_properties.thickness_properties
        height_properties = tenon_properties.height_properties

        obj = context.object
        matrix_world = obj.matrix_world
        mesh = obj.data

        if mesh.is_editmode:
            # Gain direct access to the mesh
            bm = bmesh.from_edit_mesh(mesh)
        else:
            # Create a bmesh from mesh
            # (won't affect mesh, unless explicitly written back)
            bm = bmesh.new()
            bm.from_mesh(mesh)

        # Get active face
        faces = bm.faces
        face = faces.active

        # Check if face could be tenonified ...
        if not self.__check_face(face):
            return {'CANCELLED'}

        # Extract face infos
        face_to_be_transformed = FaceToBeTransformed(face)
        face_to_be_transformed.extract_features(matrix_world)

        # Init default values, look if face has changed too
        if (thickness_properties.value == -1.0 or
                (not nearly_equal(face_to_be_transformed.shortest_length,
                                  self.shortest_length))):
            thickness_properties.value = \
                face_to_be_transformed.shortest_length / 3.0
            thickness_properties.percentage = 1.0 / 3.0
            thickness_properties.centered = True
        if (height_properties.value == -1.0 or
                (not nearly_equal(face_to_be_transformed.longest_length,
                                  self.longest_length))):
            height_properties.value = (face_to_be_transformed.longest_length *
                                       2.0) / 3.0
            height_properties.percentage = 2.0 / 3.0
            height_properties.centered = True
        if (tenon_properties.depth_value == -1.0 or
                (not nearly_equal(face_to_be_transformed.longest_length,
                                  self.longest_length))):
            tenon_properties.depth_value = \
                face_to_be_transformed.shortest_length
            haunch_properties = height_properties.haunch_first_side
            haunch_properties.depth_value = \
                tenon_properties.depth_value / 3.0
            haunch_properties.depth_percentage = 1.0 / 3.0
            haunch_properties = height_properties.haunch_second_side
            haunch_properties.depth_value = \
                tenon_properties.depth_value / 3.0
            haunch_properties.depth_percentage = 1.0 / 3.0

        # used to reinit default values when face changes
        self.shortest_length = face_to_be_transformed.shortest_length
        self.longest_length = face_to_be_transformed.longest_length

        # If percentage specified, compute length values
        if thickness_properties.type == "percentage":
            thickness_properties.value = \
                face_to_be_transformed.shortest_length * \
                thickness_properties.percentage

        if height_properties.type == "percentage":
            height_properties.value = face_to_be_transformed.longest_length * \
                height_properties.percentage

        # Init values linked to shoulder size
        if thickness_properties.centered:
            thickness_properties.shoulder_value = ((
                face_to_be_transformed.shortest_length -
                thickness_properties.value) / 2.0)
            thickness_properties.shoulder_percentage = \
                thickness_properties.shoulder_value / \
                face_to_be_transformed.shortest_length
        if height_properties.centered:
            height_properties.shoulder_value = ((
                face_to_be_transformed.longest_length -
                height_properties.value) / 2.0)
            height_properties.shoulder_percentage = \
                height_properties.shoulder_value / \
                face_to_be_transformed.longest_length

        # If shoulder percentage specified, compute length values
        if thickness_properties.shoulder_type == "percentage":
            thickness_properties.shoulder_value = \
                face_to_be_transformed.shortest_length * \
                thickness_properties.shoulder_percentage
            if (thickness_properties.shoulder_value +
                    thickness_properties.value >
                    face_to_be_transformed.shortest_length):
                thickness_properties.value = \
                    face_to_be_transformed.shortest_length - \
                    thickness_properties.shoulder_value
                thickness_properties.percentage =\
                    thickness_properties.value / \
                    face_to_be_transformed.shortest_length

        if height_properties.shoulder_type == "percentage":
            height_properties.shoulder_value = \
                face_to_be_transformed.longest_length * \
                height_properties.shoulder_percentage
            if (height_properties.shoulder_value + height_properties.value >
                    face_to_be_transformed.longest_length):
                height_properties.value = \
                    face_to_be_transformed.longest_length - \
                    height_properties.shoulder_value
                height_properties.percentage = \
                    height_properties.value / \
                    face_to_be_transformed.longest_length

        if height_properties.haunch_first_side:
            haunch_properties = height_properties.haunch_first_side
            if haunch_properties.type == "percentage":
                haunch_properties.depth_value = \
                    tenon_properties.depth_value * \
                    haunch_properties.depth_percentage

        if height_properties.haunched_second_side:
            haunch_properties = height_properties.haunch_second_side
            if haunch_properties.type == "percentage":
                haunch_properties.depth_value = \
                    tenon_properties.depth_value * \
                    haunch_properties.depth_percentage

        # Check input values
        total_length = height_properties.shoulder_value + \
            height_properties.value
        if ((not nearly_equal(total_length,
                              face_to_be_transformed.longest_length)) and
                (total_length > face_to_be_transformed.longest_length)):
            self.report({'ERROR_INVALID_INPUT'},
                        "Size of length size shoulder and tenon height are "
                        "too long.")
            return {'CANCELLED'}

        total_length = thickness_properties.shoulder_value + \
            thickness_properties.value
        if ((not nearly_equal(total_length,
                              face_to_be_transformed.shortest_length)) and
                (total_length > face_to_be_transformed.shortest_length)):
            self.report({'ERROR_INVALID_INPUT'},
                        "Size of width size shoulder and tenon thickness are "
                        "too long.")
            return {'CANCELLED'}

        # Create tenon
        tenon_builder = TenonMortiseBuilder(
            face_to_be_transformed,
            tenon_properties)
        tenon_builder.create(bm, matrix_world)

        # Flush selection
        bm.select_flush_mode()

        if mesh.is_editmode:
            bmesh.update_edit_mesh(mesh)
        else:
            bm.to_mesh(mesh)
            mesh.update()

        return {'FINISHED'}


def register():
    bpy.utils.register_class(TenonOperator)


def unregister():
    bpy.utils.unregister_class(TenonOperator)


# ----------------------------------------------
# Code to run the script alone
# ----------------------------------------------
if __name__ == "__main__":
    register()
