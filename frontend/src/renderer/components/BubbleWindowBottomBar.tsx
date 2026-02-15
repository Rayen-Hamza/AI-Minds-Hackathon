export const BubbleWindowBottomBar: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  return (
    <div className="bubble-bottom-bar">
      {children}
    </div>
  );
};
